"""
02_analyze.py
Kentucky vs border-state hospital capacity strain, Aug 2020 - Apr 2024.
Needs only pandas and numpy. Writes tables to outputs/ and Tableau-ready extracts to tableau_extracts/.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data_clean"
OUT = ROOT / "outputs"
TAB = ROOT / "tableau_extracts"
OUT.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)
rng = np.random.default_rng(2026)

PEERS = ["IL", "IN", "MO", "OH", "TN", "VA", "WV"]
STATES = ["KY"] + PEERS
WAVES = {
    "Winter 2020-21": ("2020-10-18", "2021-02-28"),
    "Delta 2021": ("2021-07-25", "2021-11-14"),
    "Omicron 2021-22": ("2021-12-12", "2022-03-06"),
}
HIGH = 0.90          # ICU strain threshold
WARN = 0.85
facts = {}           # headline numbers for the README / dashboard

h = pd.read_csv(CLEAN / "hospital_week_clean.csv.gz", low_memory=False, parse_dates=["collection_week"])
h["hospital_pk"] = h["hospital_pk"].astype(str)
st = pd.read_csv(CLEAN / "state_week_clean.csv", parse_dates=["week"])
h = h.rename(columns={"collection_week": "week"})
h["group"] = np.where(h["state"] == "KY", "Kentucky", "Border states")


def wave_of(d):
    for k, (a, b) in WAVES.items():
        if pd.Timestamp(a) <= d <= pd.Timestamp(b):
            return k
    return None


h["wave"] = h["week"].map(wave_of)

# ------------------------------------------------------------------------------------
# A. State-week weighted occupancy (sum used / sum staffed beds)
# ------------------------------------------------------------------------------------
def weighted(df, used, beds, occ):
    d = df[df[occ].notna()]
    return pd.Series({"used": d[used].sum(), "beds": d[beds].sum(), "n": d["hospital_pk"].nunique()})

icu = h[h["icu_occ"].notna()].groupby(["state", "week"]).agg(icu_used=("icu_used", "sum"), icu_beds=("icu_beds", "sum"),
                                                              icu_hosp=("hospital_pk", "nunique")).reset_index()
icu["icu_occ"] = icu["icu_used"] / icu["icu_beds"]
inp = h[h["inp_occ"].notna()].groupby(["state", "week"]).agg(inp_used=("inp_used", "sum"), inp_beds=("inp_beds", "sum"),
                                                              inp_hosp=("hospital_pk", "nunique")).reset_index()
inp["inp_occ"] = inp["inp_used"] / inp["inp_beds"]
cov = h[h["inp_covid"].notna() & h["inp_used"].notna()].groupby(["state", "week"]).agg(
    covid=("inp_covid", "sum"), used=("inp_used", "sum")).reset_index()
cov["covid_share"] = cov["covid"] / cov["used"]
sw = icu.merge(inp, on=["state", "week"], how="outer").merge(cov[["state", "week", "covid_share"]], on=["state", "week"], how="left")
sw["wave"] = sw["week"].map(wave_of)
sw = sw.merge(st[["state", "week", "staff_short_share", "staff_reporting_n", "icu_util", "inp_util"]].rename(
    columns={"icu_util": "state_file_icu_util", "inp_util": "state_file_inp_util"}), on=["state", "week"], how="left")
sw.to_csv(OUT / "state_week_occupancy.csv", index=False)
sw.to_csv(TAB / "state_week_occupancy.csv", index=False)

# cross-check: facility roll-up vs HHS's own state-level utilization
chk = sw.dropna(subset=["icu_occ", "state_file_icu_util"])
facts["rollup_vs_state_file_icu_corr"] = float(np.corrcoef(chk["icu_occ"], chk["state_file_icu_util"])[0, 1])
facts["rollup_vs_state_file_icu_mean_abs_gap_pts"] = float((chk["icu_occ"] - chk["state_file_icu_util"]).abs().mean() * 100)

# wave verification: does each wave contain the KY COVID-share peak?
ver = []
ky = sw[sw["state"] == "KY"].set_index("week")
for k, (a, b) in WAVES.items():
    seg = ky.loc[a:b]
    ver.append({"wave": k, "ky_peak_icu_week": str(seg["icu_occ"].idxmax().date()), "ky_peak_icu": float(seg["icu_occ"].max()),
                "ky_peak_covid_share_week": str(seg["covid_share"].idxmax().date()), "ky_peak_covid_share": float(seg["covid_share"].max())})
pd.DataFrame(ver).to_csv(OUT / "wave_verification.csv", index=False)

# ------------------------------------------------------------------------------------
# B. Peaks per state and wave
# ------------------------------------------------------------------------------------
rows = []
for s in STATES:
    for k, (a, b) in WAVES.items():
        seg = sw[(sw["state"] == s) & (sw["week"] >= a) & (sw["week"] <= b)].dropna(subset=["icu_occ"])
        rows.append({"state": s, "wave": k, "peak_icu_occ": seg["icu_occ"].max(),
                     "peak_week": seg.loc[seg["icu_occ"].idxmax(), "week"].date(),
                     "mean_icu_occ": seg["icu_occ"].mean(),
                     "weeks_icu_ge_85": int((seg["icu_occ"] >= WARN).sum()),
                     "weeks_icu_ge_90": int((seg["icu_occ"] >= HIGH).sum()),
                     "peak_inp_occ": sw[(sw["state"] == s) & (sw["week"] >= a) & (sw["week"] <= b)]["inp_occ"].max()})
peaks = pd.DataFrame(rows)
peaks["rank_peak_icu_among_8"] = peaks.groupby("wave")["peak_icu_occ"].rank(ascending=False).astype(int)
peaks.to_csv(OUT / "wave_peaks.csv", index=False)
peaks.to_csv(TAB / "wave_peaks.csv", index=False)

# ------------------------------------------------------------------------------------
# C. Hospital-level strain, Kentucky vs border states (stable reporters with an ICU)
# ------------------------------------------------------------------------------------
def hosp_table(d, label):
    t = d.groupby("hospital_pk").agg(
        state=("state", "first"), name=("hospital_name", "first"), side=("ky_side", "first"),
        subtype=("hospital_subtype", "first"), ownership=("ownership", "first"),
        icu_beds_median=("icu_beds", "median"), valid_weeks=("icu_occ", "count"),
        mean_icu_occ=("icu_occ", "mean"),
        share_ge90=("icu_occ", lambda s: (s[s.notna()] >= HIGH).mean()),
        share_ge85=("icu_occ", lambda s: (s[s.notna()] >= WARN).mean())).reset_index()
    t["analysis"] = label
    return t

base = h[h["stable_reporter"] & h["icu_occ"].notna() & (h["icu_beds"] > 0)]
ht = hosp_table(base, "main")
ht = ht[ht["valid_weeks"] >= 52]
ht["group"] = np.where(ht["state"] == "KY", "Kentucky", "Border states")
ht.to_csv(OUT / "hospital_strain.csv", index=False)
ht.to_csv(TAB / "hospital_strain.csv", index=False)
facts["n_hosp_ky"] = int((ht.group == "Kentucky").sum())
facts["n_hosp_peers"] = int((ht.group == "Border states").sum())


def boot_diff(a, b, n=5000, stat=np.mean):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = stat(a) - stat(b)
    bs = [stat(rng.choice(a, len(a))) - stat(rng.choice(b, len(b))) for _ in range(n)]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    pooled = np.concatenate([a, b])
    cnt = 0
    for _ in range(n):
        rng.shuffle(pooled)
        if abs(stat(pooled[:len(a)]) - stat(pooled[len(a):])) >= abs(d):
            cnt += 1
    return d, lo, hi, (cnt + 1) / (n + 1)

res = []
for metric in ["share_ge90", "share_ge85", "mean_icu_occ"]:
    a = ht.loc[ht.group == "Kentucky", metric]
    b = ht.loc[ht.group == "Border states", metric]
    d, lo, hi, p = boot_diff(a, b)
    res.append({"comparison": "Kentucky minus border states", "metric": metric, "ky_mean": a.mean(), "peers_mean": b.mean(),
                "ky_median": a.median(), "peers_median": b.median(), "diff": d, "ci_lo": lo, "ci_hi": hi, "perm_p": p,
                "n_ky": len(a), "n_peers": len(b)})
# by state
bystate = ht.groupby("state").agg(n=("hospital_pk", "count"), mean_share_ge90=("share_ge90", "mean"),
                                  median_share_ge90=("share_ge90", "median"), mean_icu_occ=("mean_icu_occ", "mean")).reset_index()
bystate["ci_lo"] = np.nan
bystate["ci_hi"] = np.nan
for i, r in bystate.iterrows():
    v = ht.loc[ht.state == r["state"], "share_ge90"].values
    bs = [rng.choice(v, len(v)).mean() for _ in range(3000)]
    bystate.loc[i, ["ci_lo", "ci_hi"]] = np.percentile(bs, [2.5, 97.5])
bystate.to_csv(OUT / "strain_by_state.csv", index=False)

# per-wave version
wres = []
for k in WAVES:
    d = h[h["stable_reporter"] & h["icu_occ"].notna() & (h["icu_beds"] > 0) & (h["wave"] == k)]
    t = d.groupby("hospital_pk").agg(state=("state", "first"), s90=("icu_occ", lambda s: (s >= HIGH).mean()), n=("icu_occ", "count"))
    t = t[t["n"] >= 8]
    a = t.loc[t.state == "KY", "s90"]
    b = t.loc[t.state != "KY", "s90"]
    dd, lo, hi, p = boot_diff(a, b, n=3000)
    wres.append({"comparison": k, "metric": "share_ge90_in_wave", "ky_mean": a.mean(), "peers_mean": b.mean(), "diff": dd,
                 "ci_lo": lo, "ci_hi": hi, "perm_p": p, "n_ky": len(a), "n_peers": len(b)})

# ------------------------------------------------------------------------------------
# D. Kentucky Lexington-side vs Louisville-side
# ------------------------------------------------------------------------------------
kyh = ht[ht.group == "Kentucky"]
a = kyh.loc[kyh.side == "Lexington-side", "share_ge90"]
b = kyh.loc[kyh.side == "Louisville-side", "share_ge90"]
d, lo, hi, p = boot_diff(a, b)
res.append({"comparison": "Lexington-side minus Louisville-side", "metric": "share_ge90", "ky_mean": a.mean(), "peers_mean": b.mean(),
            "ky_median": a.median(), "peers_median": b.median(), "diff": d, "ci_lo": lo, "ci_hi": hi, "perm_p": p,
            "n_ky": len(a), "n_peers": len(b)})
pd.DataFrame(res + wres).to_csv(OUT / "ky_vs_peers_tests.csv", index=False)

kside = h[(h.state == "KY") & h["icu_occ"].notna()].groupby(["ky_side", "week"]).agg(
    icu_used=("icu_used", "sum"), icu_beds=("icu_beds", "sum"), hosp=("hospital_pk", "nunique"),
    n_ge90=("icu_occ", lambda s: int((s >= HIGH).sum()))).reset_index()
kside["icu_occ"] = kside["icu_used"] / kside["icu_beds"]
kside["share_hosp_ge90"] = kside["n_ge90"] / kside["hosp"]
kside.to_csv(OUT / "ky_side_week.csv", index=False)
kside.to_csv(TAB / "ky_side_week.csv", index=False)
# timing: does one side lead the other? cross-correlation of weekly occupancy
piv = kside.pivot(index="week", columns="ky_side", values="icu_occ").dropna()
xc = {}
for lag in range(-6, 7):
    xc[lag] = float(piv["Lexington-side"].corr(piv["Louisville-side"].shift(lag)))
facts["ky_side_xcorr_best_lag_weeks"] = int(max(xc, key=xc.get))
facts["ky_side_xcorr_at_0"] = xc[0]
facts["ky_side_xcorr_best"] = xc[facts["ky_side_xcorr_best_lag_weeks"]]
peak_side = {k: str(piv[k].loc["2020-10-18":"2022-03-06"].idxmax().date()) for k in piv.columns}
facts["ky_side_peak_weeks"] = peak_side
side_waves = []
for k, (a_, b_) in WAVES.items():
    seg = piv.loc[a_:b_]
    side_waves.append({"wave": k, **{f"{c}_peak": float(seg[c].max()) for c in seg.columns},
                       **{f"{c}_peak_week": str(seg[c].idxmax().date()) for c in seg.columns}})
pd.DataFrame(side_waves).to_csv(OUT / "ky_side_wave_peaks.csv", index=False)

# ------------------------------------------------------------------------------------
# E. ICU size effect
# ------------------------------------------------------------------------------------
ht["icu_size"] = pd.cut(ht["icu_beds_median"], [0, 8, 20, 10000], labels=["Small: 8 beds or fewer", "Medium: 9-20", "Large: over 20"])
size = ht.groupby(["group", "icu_size"], observed=True).agg(n=("hospital_pk", "count"), mean_share_ge90=("share_ge90", "mean"),
                                                             median_share_ge90=("share_ge90", "median"),
                                                             mean_icu_occ=("mean_icu_occ", "mean")).reset_index()
size.to_csv(OUT / "strain_by_icu_size.csv", index=False)

# ------------------------------------------------------------------------------------
# F. Headroom within 60 miles (Kentucky only): strained hospital with no open ICU beds nearby
# ------------------------------------------------------------------------------------
def hav(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    aa = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(aa))

kyall = h[(h.state == "KY") & h["icu_occ"].notna() & (h["icu_beds"] > 0) & h["lat"].notna()].copy()
coords = kyall.drop_duplicates("hospital_pk").set_index("hospital_pk")[["lat", "lon"]]
ids = coords.index.tolist()
D = pd.DataFrame(hav(coords["lat"].values[:, None], coords["lon"].values[:, None],
                     coords["lat"].values[None, :], coords["lon"].values[None, :]), index=ids, columns=ids)
RADIUS, LOW, MIN_BEDS = 60, 0.80, 2
hw = []
for wk, g in kyall.groupby("week"):
    g = g.set_index("hospital_pk")
    strained = g[g["icu_occ"] >= HIGH]
    if strained.empty:
        hw.append({"week": wk, "hospitals": len(g), "strained": 0, "stranded": 0, "median_open_beds_nearby": np.nan,
                   "open_beds_all_ky": float((g["icu_beds"] - g["icu_used"]).clip(lower=0).sum())})
        continue
    opens = []
    for pk in strained.index:
        near = [i for i in g.index if i != pk and D.loc[pk, i] <= RADIUS and g.loc[i, "icu_occ"] < LOW]
        opens.append(float((g.loc[near, "icu_beds"] - g.loc[near, "icu_used"]).clip(lower=0).sum()) if near else 0.0)
    opens = np.array(opens)
    hw.append({"week": wk, "hospitals": len(g), "strained": len(strained), "stranded": int((opens < MIN_BEDS).sum()),
               "median_open_beds_nearby": float(np.median(opens)),
               "open_beds_all_ky": float((g["icu_beds"] - g["icu_used"]).clip(lower=0).sum())})
hw = pd.DataFrame(hw)
hw["wave"] = hw["week"].map(wave_of)
hw["stranded_share"] = hw["stranded"] / hw["strained"].replace(0, np.nan)
hw.to_csv(OUT / "ky_headroom_week.csv", index=False)
hw.to_csv(TAB / "ky_headroom_week.csv", index=False)
tot_strained = int(hw["strained"].sum())
tot_stranded = int(hw["stranded"].sum())
facts["headroom_strained_hospital_weeks"] = tot_strained
facts["headroom_stranded_hospital_weeks"] = tot_stranded
facts["headroom_stranded_share"] = tot_stranded / tot_strained if tot_strained else None
hwv = []
for k in WAVES:
    z = hw[hw.wave == k]
    hwv.append({"wave": k, "strained_hospital_weeks": int(z.strained.sum()), "stranded_hospital_weeks": int(z.stranded.sum()),
                "stranded_share": float(z.stranded.sum() / z.strained.sum()) if z.strained.sum() else np.nan,
                "peak_strained_hospitals_in_one_week": int(z.strained.max()),
                "median_open_beds_nearby_when_strained": float(z["median_open_beds_nearby"].median())})
pd.DataFrame(hwv).to_csv(OUT / "ky_headroom_by_wave.csv", index=False)

# ------------------------------------------------------------------------------------
# G. Staffing shortage vs ICU strain (state level)
# ------------------------------------------------------------------------------------
sp = sw.dropna(subset=["icu_occ", "staff_short_share"]).copy()
lagres = []
for lag in range(-4, 9):
    xs, ys = [], []
    for s in STATES:
        d = sp[sp.state == s].set_index("week").sort_index()
        x = d["icu_occ"]
        y = d["staff_short_share"].shift(-lag)       # staffing `lag` weeks after occupancy
        m = x.notna() & y.notna()
        xs.append((x[m] - x[m].mean()).values)
        ys.append((y[m] - y[m].mean()).values)
    xs, ys = np.concatenate(xs), np.concatenate(ys)
    lagres.append({"lag_weeks_staffing_after_icu": lag, "corr": float(np.corrcoef(xs, ys)[0, 1]), "n": len(xs)})
lagres = pd.DataFrame(lagres)
lagres.to_csv(OUT / "staffing_lag_corr.csv", index=False)
facts["staffing_best_lag"] = int(lagres.loc[lagres["corr"].idxmax(), "lag_weeks_staffing_after_icu"])
facts["staffing_best_corr"] = float(lagres["corr"].max())
facts["staffing_corr_lag0"] = float(lagres.loc[lagres.lag_weeks_staffing_after_icu == 0, "corr"].iloc[0])
stf = st[st.state.isin(STATES)].copy()
stf_peak = stf.groupby("state").agg(peak_share=("staff_short_share", "max"), mean_share=("staff_short_share", "mean")).reset_index()
nat = st.groupby("state")["staff_short_share"].max()
facts["staff_peak_share_ky"] = float(stf_peak.loc[stf_peak.state == "KY", "peak_share"].iloc[0])
facts["staff_peak_share_national_median_of_states"] = float(nat.median())
stf_peak.to_csv(OUT / "staffing_peaks.csv", index=False)
stf.to_csv(TAB / "state_week_staffing.csv", index=False)

# ------------------------------------------------------------------------------------
# H. Forecast test: one week ahead, Kentucky ICU occupancy, rolling origin
# ------------------------------------------------------------------------------------
y = sw[sw.state == "KY"].set_index("week").sort_index()["icu_occ"].dropna()
cs = sw[sw.state == "KY"].set_index("week").sort_index()["covid_share"].reindex(y.index).ffill()
df = pd.DataFrame({"y": y, "d1": y.diff(), "d2": y.diff().shift(1), "dev4": y - y.rolling(4).mean(), "cov": cs, "dcov": cs.diff()})
df["target"] = y.shift(-1) - y
df = df.dropna()
feat = ["d1", "d2", "dev4", "dcov"]
preds_m, preds_n, act, wk_list = [], [], [], []
START = 52
for i in range(START, len(df)):
    tr = df.iloc[:i]
    X = np.column_stack([np.ones(len(tr)), tr[feat].values])
    lam = 1e-3
    beta = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ tr["target"].values)
    x0 = np.concatenate([[1], df.iloc[i][feat].values])
    preds_m.append(df.iloc[i]["y"] + x0 @ beta)
    preds_n.append(df.iloc[i]["y"])
    act.append(df.iloc[i]["y"] + df.iloc[i]["target"])
    wk_list.append(df.index[i])
fc = pd.DataFrame({"week_origin": wk_list, "actual_next": act, "naive": preds_n, "model": preds_m})
fc["err_naive"] = (fc["actual_next"] - fc["naive"]).abs()
fc["err_model"] = (fc["actual_next"] - fc["model"]).abs()
fc["surge"] = fc["actual_next"] >= WARN
fc.to_csv(OUT / "forecast_ky_icu.csv", index=False)
diff = fc["err_naive"] - fc["err_model"]
blocks = [diff.values[i:i + 8] for i in range(0, len(diff), 8)]
bm = [np.concatenate([blocks[j] for j in rng.integers(0, len(blocks), len(blocks))]).mean() for _ in range(3000)]
facts["forecast_n_weeks"] = len(fc)
facts["forecast_mae_naive_pts"] = float(fc["err_naive"].mean() * 100)
facts["forecast_mae_model_pts"] = float(fc["err_model"].mean() * 100)
facts["forecast_mae_gain_pts"] = float(diff.mean() * 100)
facts["forecast_gain_ci_pts"] = [float(np.percentile(bm, 2.5) * 100), float(np.percentile(bm, 97.5) * 100)]
facts["forecast_surge_weeks"] = int(fc["surge"].sum())
facts["forecast_mae_naive_surge_pts"] = float(fc.loc[fc.surge, "err_naive"].mean() * 100)
facts["forecast_mae_model_surge_pts"] = float(fc.loc[fc.surge, "err_model"].mean() * 100)

# ------------------------------------------------------------------------------------
# I. Sensitivity of the headline result
# ------------------------------------------------------------------------------------
def headline(d, thr=HIGH, min_weeks=52):
    d = d[d["icu_occ"].notna() & (d["icu_beds"] > 0)]
    t = d.groupby("hospital_pk").agg(state=("state", "first"), n=("icu_occ", "count"),
                                     s=("icu_occ", lambda s: (s >= thr).mean()))
    t = t[t["n"] >= min_weeks]
    a, b = t.loc[t.state == "KY", "s"], t.loc[t.state != "KY", "s"]
    dd, lo, hi, p = boot_diff(a, b, n=2000)
    return {"ky": a.mean(), "peers": b.mean(), "diff": dd, "ci_lo": lo, "ci_hi": hi, "p": p, "n_ky": len(a), "n_peers": len(b)}

sens = []
allw = h[h["icu_occ"].notna()]
sens.append({"scenario": "Main analysis (stable reporters, 90% threshold)", **headline(allw[allw.stable_reporter])})
sens.append({"scenario": "Drop bed-count blips and rows above 100%", **headline(allw[allw.stable_reporter & ~allw.flag_cap_shift & ~allw.flag_over100])})
sens.append({"scenario": "Threshold 85% instead of 90%", **headline(allw[allw.stable_reporter], thr=WARN)})
sens.append({"scenario": "Require 100+ valid weeks", **headline(allw[allw.stable_reporter], min_weeks=100)})
sens.append({"scenario": "Critical access hospitals only", **headline(allw[allw.stable_reporter & (allw.hospital_subtype == "Critical Access Hospitals")], min_weeks=52)})
sens.append({"scenario": "Short term (acute) hospitals only", **headline(allw[allw.stable_reporter & (allw.hospital_subtype == "Short Term")])})
sens.append({"scenario": "Kentucky vs Tennessee and Virginia only", **headline(allw[allw.stable_reporter & allw.state.isin(["KY", "TN", "VA"])])})
pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)

# ------------------------------------------------------------------------------------
# J. Data-quality figure inputs
# ------------------------------------------------------------------------------------
dq = h.groupby("week").agg(rows=("hospital_pk", "count"), icu_valid=("icu_occ", "count"),
                           spikes=("flag_spike", "sum"), blips=("flag_cap_shift", "sum"), over100=("flag_over100", "sum")).reset_index()
dq.to_csv(OUT / "data_quality_by_week.csv", index=False)
h[(h.state == "KY")].to_csv(TAB / "ky_hospital_week.csv", index=False)

facts["window"] = [str(h["week"].min().date()), str(h["week"].max().date())]
facts["n_hospitals_total"] = int(h["hospital_pk"].nunique())
with open(OUT / "headline_facts.json", "w") as fh:
    json.dump(facts, fh, indent=2, default=str)
print(json.dumps(facts, indent=2, default=str))
print(pd.DataFrame(res + wres).round(3).to_string())
print(bystate.round(3).to_string())
print(peaks[peaks.state == "KY"].round(3).to_string())
print(pd.DataFrame(sens).round(3).to_string())
print(size.round(3).to_string())
print(pd.DataFrame(hwv).round(3).to_string())
print(lagres.round(3).to_string())
print(pd.DataFrame(ver).round(3).to_string())
print(pd.DataFrame(side_waves).round(3).to_string())
