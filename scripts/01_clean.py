"""
01_clean.py
Clean the HHS facility-level hospital capacity file (Kentucky + 7 border states),
the HHS state-level daily timeseries, and join CMS Hospital General Information.

Every cleaning step writes one row to docs/cleaning_log.csv:
step, what_was_done, rows_before, rows_after, values_affected, why
"""
import re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
OUT = ROOT / "data_clean"
DOCS = ROOT / "docs"
OUT.mkdir(exist_ok=True)
DOCS.mkdir(exist_ok=True)

STATES = ["KY", "IL", "IN", "MO", "OH", "TN", "VA", "WV"]
log = []


def note(step, what, before, after, affected, why):
    log.append(dict(step=step, what_was_done=what, rows_before=before, rows_after=after,
                    values_affected=affected, why=why))


# --------------------------------------------------------------------------------------
# 1. Facility file
# --------------------------------------------------------------------------------------
f = pd.read_csv(RAW / "anag-cw7u.csv", low_memory=False)
n0 = len(f)
note("1.0", "Loaded raw facility file (KY + 7 border states)", n0, n0, 0,
     "Starting point. 128 columns, one row per hospital per week.")

f["collection_week"] = pd.to_datetime(f["collection_week"])
dups = f.duplicated(["hospital_pk", "collection_week"]).sum()
f = f.sort_values(["hospital_pk", "collection_week", "is_corrected"]).drop_duplicates(
    ["hospital_pk", "collection_week"], keep="last")
note("1.1", "Checked duplicate hospital-week rows (kept the corrected row if any)", n0, len(f), int(dups),
     "Each hospital should appear once per week.")

KEEP = {
    "inpatient_beds_7_day_avg": "inp_beds",
    "inpatient_beds_used_7_day_avg": "inp_used",
    "inpatient_beds_used_covid_7_day_avg": "inp_covid",
    "total_staffed_adult_icu_beds_7_day_avg": "icu_beds",
    "staffed_adult_icu_bed_occupancy_7_day_avg": "icu_used",
    "staffed_icu_adult_patients_confirmed_and_suspected_covid_7_day_avg": "icu_covid",
}
COVER = {
    "inpatient_beds_7_day_coverage": "cov_inp_beds",
    "inpatient_beds_used_7_day_coverage": "cov_inp_used",
    "inpatient_beds_used_covid_7_day_coverage": "cov_inp_covid",
    "total_staffed_adult_icu_beds_7_day_coverage": "cov_icu_beds",
    "staffed_adult_icu_bed_occupancy_7_day_coverage": "cov_icu_used",
    "staffed_icu_adult_patients_confirmed_and_suspected_covid_7_day_coverage": "cov_icu_covid",
}
base_cols = ["hospital_pk", "collection_week", "state", "ccn", "hospital_name", "city", "zip",
             "hospital_subtype", "fips_code", "is_metro_micro", "geocoded_hospital_address", "is_corrected"]
f = f[base_cols + list(KEEP) + list(COVER)].rename(columns={**KEEP, **COVER})

# 1.2 suppression code
supp_total = 0
for c in KEEP.values():
    m = f[c] == -999999
    supp_total += int(m.sum())
    f.loc[m, c] = np.nan
neg_other = int((f[list(KEEP.values())] < 0).sum().sum())
note("1.2", "Replaced the HHS suppression code -999999 with missing", len(f), len(f), supp_total,
     "HHS uses -999999 for small counts it suppressed. Left as a number it would crush every average. "
     f"Other negative values after this step: {neg_other}.")

# 1.3 scope: acute-care style hospitals only
before = len(f)
sub_counts = f["hospital_subtype"].value_counts().to_dict()
f = f[f["hospital_subtype"].isin(["Short Term", "Critical Access Hospitals"])].copy()
note("1.3", "Kept Short Term and Critical Access hospitals; dropped Long Term and Children's hospitals",
     before, len(f), before - len(f),
     f"Adult ICU and general inpatient capacity is not comparable for long-term or children's hospitals. Raw mix: {sub_counts}")

# 1.4 reporting-days coverage (7 = reported all 7 days that week)
before = len(f)
aff = 0
pairs = [("inp_used", "cov_inp_used"), ("inp_beds", "cov_inp_beds"), ("inp_covid", "cov_inp_covid"),
         ("icu_used", "cov_icu_used"), ("icu_beds", "cov_icu_beds"), ("icu_covid", "cov_icu_covid")]
for v, c in pairs:
    m = f[c].fillna(0) < 4
    aff += int((m & f[v].notna()).sum())
    f.loc[m, v] = np.nan
note("1.4", "Set a measure to missing when the hospital reported it on fewer than 4 of the 7 days",
     before, len(f), aff,
     "A 7-day average built from 1 to 3 days is a weak estimate. Rule: need at least 4 reporting days.")

# 1.5 geocode
pt = f["geocoded_hospital_address"].str.extract(r"POINT \((-?\d+\.?\d*) (-?\d+\.?\d*)\)")
f["lon"] = pd.to_numeric(pt[0])
f["lat"] = pd.to_numeric(pt[1])
note("1.5", "Parsed latitude and longitude from the geocoded address", len(f), len(f),
     int(f["lat"].isna().sum()), "Needed for the Lexington-side / Louisville-side rule. Rows without a geocode keep no region.")

# 1.6 occupancy and impossible values
f["inp_occ"] = np.where(f["inp_beds"] > 0, f["inp_used"] / f["inp_beds"], np.nan)
f["icu_occ"] = np.where(f["icu_beds"] > 0, f["icu_used"] / f["icu_beds"], np.nan)
zero_den = int(((f["inp_beds"] <= 0) | (f["icu_beds"] <= 0)).sum())
over1 = int(((f["inp_occ"] > 1) | (f["icu_occ"] > 1)).sum())
bad = (f["inp_occ"] > 1.5) | (f["icu_occ"] > 1.5)
for c in ["inp_occ", "icu_occ"]:
    f.loc[f[c] > 1.5, c] = np.nan
note("1.6", "Computed occupancy = beds used / beds staffed. Zero-bed denominators left missing; occupancy above 150% set to missing",
     len(f), len(f), int(bad.sum()),
     f"Over 100% can be real (surge beds), so values from 100% to 150% are kept and flagged ({over1} rows were above 100% before the 150% cut). "
     f"Above 150% is treated as a reporting error. Zero-bed denominators: {zero_den} rows.")

# 1.7 outlier flags
f = f.sort_values(["hospital_pk", "collection_week"]).reset_index(drop=True)
g = f.groupby("hospital_pk")
f["icu_prev"] = g["icu_occ"].shift(1)
f["icu_next"] = g["icu_occ"].shift(-1)
d1 = f["icu_occ"] - f["icu_prev"]
d2 = f["icu_occ"] - f["icu_next"]
f["flag_spike"] = ((d1.abs() > 0.35) & (d2.abs() > 0.35) & (np.sign(d1) == np.sign(d2))).fillna(False)
f["inp_prev"] = g["inp_occ"].shift(1)
f["inp_next"] = g["inp_occ"].shift(-1)
e1 = f["inp_occ"] - f["inp_prev"]
e2 = f["inp_occ"] - f["inp_next"]
f["flag_spike_inp"] = ((e1.abs() > 0.35) & (e2.abs() > 0.35) & (np.sign(e1) == np.sign(e2))).fillna(False)

def local_flag(s):
    """One-off blip: more than 50% and at least 3 beds away from the hospital's own 9-week centered median."""
    med = s.rolling(9, center=True, min_periods=5).median()
    return ((s / med - 1).abs() > 0.5) & ((s - med).abs() >= 3)

def global_flag(s):
    med = s.median()
    return ((s / med - 1).abs() > 0.5) & ((s - med).abs() >= 3) if med > 0 else pd.Series(False, index=s.index)

f["flag_cap_shift"] = (g["icu_beds"].transform(local_flag).fillna(False).astype(bool) |
                       g["inp_beds"].transform(local_flag).fillna(False).astype(bool))
f["_glob"] = (g["icu_beds"].transform(global_flag).fillna(False).astype(bool) |
              g["inp_beds"].transform(global_flag).fillna(False).astype(bool))
level_shift_hosp = int((f.groupby("hospital_pk")["_glob"].sum() >= 8).sum())
f = f.drop(columns=["_glob"])
n_spike = int((f["flag_spike"] | f["flag_spike_inp"]).sum())
n_cap = int(f["flag_cap_shift"].sum())
f["flag_over100"] = ((f["inp_occ"] > 1) | (f["icu_occ"] > 1)).fillna(False)
f["main_ok"] = ~(f["flag_spike"] | f["flag_spike_inp"])
note("1.7", "Flagged outliers three ways: isolated one-week occupancy spikes, one-off bed-count blips, and occupancy above 100%",
     len(f), len(f), n_spike + n_cap,
     f"Isolated spike = jumps by more than 35 points and snaps back the next week ({n_spike} rows). "
     f"Bed-count blip = more than 50% and at least 3 beds away from the hospital's own surrounding 9-week median ({n_cap} rows). "
     f"{level_shift_hosp} hospitals report staffed beds more than 50% away from their own overall median for 8 or more weeks, a sustained shift such as an ICU going from 12 to 4 beds. "
     "Staffed beds move with staffing, so sustained shifts are treated as real operating changes and kept. "
     "Spikes are removed from the main analysis; bed-count blips and over-100% rows are kept and tested in a sensitivity check.")
before = len(f)
spike_vals = int((~f["main_ok"]).sum())
for c in ["icu_occ", "inp_occ"]:
    f.loc[~f["main_ok"], c] = np.nan
note("1.8", "Removed the isolated spikes from the main analysis (occupancy set to missing)", before, len(f), spike_vals,
     "A one-week jump that reverses is almost always a data-entry or reporting artifact, not a real hospital filling up and emptying in 7 days.")

# 1.9 analysis window = once reporting is stable
ever_icu = f.groupby("hospital_pk")["icu_occ"].transform(lambda s: s.notna().any())
wk = f[ever_icu].groupby("collection_week")["icu_occ"].apply(lambda s: s.notna().mean())
n_h = f["hospital_pk"].nunique()
first_stable = wk[wk >= 0.60].index.min()
last_week = f["collection_week"].max()
before = len(f)
f = f[(f["collection_week"] >= first_stable)].copy()
note("1.9", f"Limited the analysis window to {first_stable.date()} through {last_week.date()}", before, len(f),
     before - len(f),
     "Adult ICU reporting began in July 2020 and nothing valid exists before it. Window starts at the first week when at least 60% of the hospitals that ever report adult ICU data have a valid ICU occupancy value.")

# 1.10 continuity for hospital-level comparisons
valid_weeks = f.groupby("hospital_pk")["icu_occ"].apply(lambda s: s.notna().sum())
f["hosp_valid_icu_weeks"] = f["hospital_pk"].map(valid_weeks)
f["has_icu"] = f["hosp_valid_icu_weeks"] > 0
f["stable_reporter"] = f["hosp_valid_icu_weeks"] >= 52
note("1.10", "Marked hospitals with fewer than 52 valid ICU weeks as not stable reporters", len(f), len(f),
     int((~f["stable_reporter"]).sum()),
     "Hospital-level rankings and tests use stable reporters only, so a hospital with two weeks of data cannot drive a result. State totals use all valid rows.")

# 1.11 join CMS
c = pd.read_csv(RAW / "Hospital_General_Information.csv", dtype=str)
c["ccn"] = c["Facility ID"].str.zfill(6)
c = c.rename(columns={"County/Parish": "county", "Hospital Ownership": "ownership",
                      "Emergency Services": "emergency_services", "Hospital overall rating": "cms_rating",
                      "Hospital Type": "cms_type"})[["ccn", "county", "ownership", "emergency_services", "cms_rating", "cms_type"]]
f["ccn"] = f["ccn"].astype(str).str.zfill(6)
before = len(f)
f = f.merge(c, on="ccn", how="left")
matched = f["cms_type"].notna().mean()
note("1.11", "Joined CMS Hospital General Information on the 6-digit CMS certification number", before, len(f),
     int(f["cms_type"].isna().sum()),
     f"{matched:.1%} of rows matched. Unmatched rows keep their capacity data but have no county, ownership or rating.")
f["cms_rating"] = pd.to_numeric(f["cms_rating"], errors="coerce")

# 1.12 Kentucky side rule
HUBS = {"Lexington-side": (38.0298, -84.5037),   # UK Chandler Hospital area
        "Louisville-side": (38.2465, -85.7457)}  # UofL Hospital area

def hav(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))

d_lex = hav(f["lat"], f["lon"], *HUBS["Lexington-side"])
d_lou = hav(f["lat"], f["lon"], *HUBS["Louisville-side"])
f["ky_side"] = np.where(f["state"] != "KY", None,
                        np.where(d_lex.isna(), None, np.where(d_lex <= d_lou, "Lexington-side", "Louisville-side")))
f["miles_to_nearest_hub"] = np.minimum(d_lex, d_lou)
ky = f[(f["state"] == "KY")].drop_duplicates("hospital_pk")
note("1.12", "Assigned each Kentucky hospital to the Lexington-side or Louisville-side by straight-line distance to a hub in each city",
     len(f), len(f), int(ky.shape[0]),
     "ANALYST ASSUMPTION, not the official RMOCC boundary (which I could not find). "
     f"Result: {ky['ky_side'].value_counts().to_dict()} Kentucky hospitals.")

keep_out = ["hospital_pk", "ccn", "hospital_name", "city", "zip", "state", "county", "fips_code", "hospital_subtype",
            "ownership", "emergency_services", "cms_rating", "is_metro_micro", "lat", "lon", "ky_side",
            "miles_to_nearest_hub", "collection_week", "inp_beds", "inp_used", "inp_covid", "icu_beds", "icu_used",
            "icu_covid", "inp_occ", "icu_occ", "flag_over100", "flag_spike", "flag_spike_inp", "flag_cap_shift",
            "main_ok", "stable_reporter", "hosp_valid_icu_weeks"]
f[keep_out].round(4).to_csv(OUT / "hospital_week_clean.csv.gz", index=False, compression="gzip")

# --------------------------------------------------------------------------------------
# 2. State timeseries (daily -> weekly)
# --------------------------------------------------------------------------------------
s = pd.read_csv(RAW / "g62h-syeh.csv", low_memory=False)
ns0 = len(s)
s["date"] = pd.to_datetime(s["date"])
note("2.0", "Loaded raw state-level daily file (all states and territories)", ns0, ns0, 0,
     "National backdrop and the critical-staffing-shortage counts, which are only in this file.")
cols = ["state", "date", "critical_staffing_shortage_today_yes", "critical_staffing_shortage_today_no",
        "critical_staffing_shortage_today_not_reported", "inpatient_beds_utilization", "adult_icu_bed_utilization",
        "percent_of_inpatients_with_covid"]
s = s[cols].copy()
s = s[s["state"].isin(set(s["state"]) - {"AS", "GU", "MP", "PR", "VI", "DC"})].copy()
note("2.1", "Dropped territories and DC", ns0, len(s), ns0 - len(s),
     "Keep the 50 states so the national comparison is like for like.")
for c_ in ["inpatient_beds_utilization", "adult_icu_bed_utilization", "percent_of_inpatients_with_covid"]:
    bad = s[c_] > 1.5
    s.loc[bad, c_] = np.nan
    note("2.2", f"Set {c_} above 150% to missing", len(s), len(s), int(bad.sum()),
         "Same rule as the hospital file. The raw state file reaches 262% for adult ICU use, which is a reporting artifact.")
den = s["critical_staffing_shortage_today_yes"] + s["critical_staffing_shortage_today_no"]
s["staff_short_share"] = np.where(den > 0, s["critical_staffing_shortage_today_yes"] / den, np.nan)
s["staff_reporting_n"] = den
s["week"] = s["date"] - pd.to_timedelta((s["date"].dt.dayofweek + 1) % 7, unit="D")  # Sunday-start weeks
w = s[s["week"] >= first_stable].groupby(["state", "week"]).agg(
    icu_util=("adult_icu_bed_utilization", "mean"),
    inp_util=("inpatient_beds_utilization", "mean"),
    covid_share=("percent_of_inpatients_with_covid", "mean"),
    staff_short_share=("staff_short_share", "mean"),
    staff_reporting_n=("staff_reporting_n", "mean"),
    days=("date", "nunique")).reset_index()
note("2.3", "Rolled daily rows up to Sunday-start weeks to match the facility file; staffing share = hospitals reporting a critical shortage / hospitals answering yes or no",
     len(s), len(w), 0, "Same weekly grain as the facility file. Hospitals that did not answer are left out of the share rather than counted as no.")
w.round(4).to_csv(OUT / "state_week_clean.csv", index=False)

lg = pd.DataFrame(log)
cnt = {"1": 0, "2": 0}
labels = []
for st in lg["step"]:
    k = st.split(".")[0]
    cnt[k] += 1
    labels.append(("F" if k == "1" else "S") + f"{cnt[k]:02d}")
lg["step"] = labels
lg.to_csv(DOCS / "cleaning_log.csv", index=False)
print(lg[["step", "rows_before", "rows_after", "values_affected"]].to_string())
print("window", first_stable.date(), last_week.date(), "hospitals", f["hospital_pk"].nunique())
print(f.groupby("state")["hospital_pk"].nunique().to_dict())
