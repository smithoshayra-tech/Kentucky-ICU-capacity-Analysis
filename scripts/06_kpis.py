"""
Builds the KPI table with SQL (sql/04_kpi_state_week.sql), checks it against an independent pandas
calculation, and writes a weekly KPI report for the latest week in the data.
Outputs: outputs/kpi_state_week.csv, outputs/weekly_kpi_report.csv, outputs/weekly_kpi_report.md
"""
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
h = pd.read_csv(ROOT / "data_clean" / "hospital_week_clean.csv.gz", low_memory=False)
h = h.rename(columns={"collection_week": "week"})
h["week"] = h["week"].astype(str).str[:10]
s = pd.read_csv(ROOT / "data_clean" / "state_week_clean.csv")
s["week"] = s["week"].astype(str).str[:10]

con = sqlite3.connect(":memory:")
h[["hospital_pk", "state", "week", "icu_beds", "icu_used", "icu_occ"]].to_sql("hospital_week", con, index=False)
s[["state", "week", "staff_short_share"]].to_sql("state_week", con, index=False)
kpi = pd.read_sql_query((ROOT / "sql" / "04_kpi_state_week.sql").read_text(), con)
kpi.to_csv(ROOT / "outputs" / "kpi_state_week.csv", index=False)

# ---- independent check in pandas
v = h[h["icu_occ"].notna() & (h["icu_beds"] > 0)]
g = v.groupby(["state", "week"])
chk = pd.DataFrame({
    "k1": g["icu_used"].sum() / g["icu_beds"].sum(),
    "k2": g["icu_occ"].apply(lambda x: (x >= 0.90).sum()),
    "n_valid": g.size(),
})
chk["k3"] = chk["k2"] / chk["n_valid"]
ever = set(v["hospital_pk"])
rows = h[h["hospital_pk"].isin(ever)].groupby(["state", "week"]).size()
chk["k4"] = chk["n_valid"] / rows.reindex(chk.index)
m = kpi.set_index(["state", "week"]).join(chk, how="inner")
gaps = {
    "K1 icu occupancy": (m["k1_icu_occupancy"] - m["k1"]).abs().max(),
    "K2 strained hospitals": (m["k2_strained_hospitals"] - m["k2"]).abs().max(),
    "K3 share strained": (m["k3_share_hospitals_strained"] - m["k3"]).abs().max(),
    "K4 completeness": (m["k4_icu_reporting_completeness"] - m["k4"]).abs().max(),
}
for k, val in gaps.items():
    print(f"max gap {k}: {val:.6f}")
assert all(val < 1e-3 for val in gaps.values()), "SQL KPI table and pandas disagree"
print(f"OK: KPI table matches pandas ({len(m):,} state-weeks checked)")

# ---- weekly report for the latest week
latest = kpi["week"].max()
prev = sorted(kpi["week"].unique())[-5]  # four weeks earlier
cur = kpi[kpi["week"] == latest].set_index("state")
old = kpi[kpi["week"] == prev].set_index("state")
rep = pd.DataFrame({
    "icu_occupancy": cur["k1_icu_occupancy"],
    "change_vs_4_weeks_ago_pts": (cur["k1_icu_occupancy"] - old["k1_icu_occupancy"]) * 100,
    "strained_hospitals": cur["k2_strained_hospitals"],
    "share_hospitals_strained": cur["k3_share_hospitals_strained"],
    "icu_reporting_completeness": cur["k4_icu_reporting_completeness"],
    "critical_staffing_shortage_rate": cur["k5_critical_staffing_shortage_rate"],
}).round(4)
order = ["KY"] + [x for x in rep.index if x != "KY"]
rep = rep.loc[order]
rep.index.name = "state"
rep.to_csv(ROOT / "outputs" / "weekly_kpi_report.csv")

peers = rep.drop(index="KY")
lines = [
    f"# Weekly KPI report, week starting {latest}",
    "",
    "Latest week in the data (HHS reporting ended April 2024), so this is a demonstration of the report, not a live view.",
    f"Change column compares with the week starting {prev}. Definitions: docs/kpi_definitions.md.",
    "",
    "| State | ICU occupancy | Change vs 4 weeks ago (pts) | Strained hospitals (90%+) | Share of hospitals strained | ICU reporting completeness | Critical staffing shortage rate |",
    "|---|---|---|---|---|---|---|",
]
def pct(x): return "n/a" if pd.isna(x) else f"{x*100:.1f}%"
for st, r in rep.iterrows():
    chg = "n/a" if pd.isna(r["change_vs_4_weeks_ago_pts"]) else f"{r['change_vs_4_weeks_ago_pts']:+.1f}"
    lines.append(f"| {st} | {pct(r['icu_occupancy'])} | {chg} | {int(r['strained_hospitals'])} | {pct(r['share_hospitals_strained'])} | {pct(r['icu_reporting_completeness'])} | {pct(r['critical_staffing_shortage_rate'])} |")
lines += ["", f"Border-state average ICU occupancy: {pct(peers['icu_occupancy'].mean())}. Kentucky: {pct(rep.loc['KY','icu_occupancy'])}."]
(ROOT / "outputs" / "weekly_kpi_report.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
