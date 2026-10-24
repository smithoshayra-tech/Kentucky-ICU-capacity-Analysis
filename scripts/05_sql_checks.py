"""
05_sql_checks.py
Loads the cleaned hospital-week file into SQLite and re-computes two headline results with plain SQL
(sql/01 and sql/02), then compares them with the pandas results. If they disagree the script fails.
"""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
h = pd.read_csv(ROOT / "data_clean" / "hospital_week_clean.csv.gz", low_memory=False)
h = h.rename(columns={"collection_week": "week"})
h["week"] = h["week"].astype(str).str[:10]
h["stable_reporter"] = h["stable_reporter"].astype(int)
con = sqlite3.connect(":memory:")
h.to_sql("hospital_week", con, index=False)


def run(name):
    return pd.read_sql_query((ROOT / "sql" / name).read_text(), con)

a = run("01_state_strain.sql").set_index("state")
b = pd.read_csv(ROOT / "outputs" / "strain_by_state.csv").set_index("state")
gap1 = (a["mean_share_ge90"] - b["mean_share_ge90"]).abs().max()
c = run("02_state_week_peaks.sql").set_index("state")
d = pd.read_csv(ROOT / "outputs" / "wave_peaks.csv")
d = d.pivot(index="state", columns="wave", values="peak_icu_occ")
gap2 = max((c["peak_delta_2021"] - d["Delta 2021"]).abs().max(),
           (c["peak_omicron_2021_22"] - d["Omicron 2021-22"]).abs().max(),
           (c["peak_winter_2020_21"] - d["Winter 2020-21"]).abs().max())
print(a.to_string())
print(c.to_string())
print(f"max gap, share at 90%+ (SQL vs pandas): {gap1:.6f}")
print(f"max gap, wave peaks (SQL vs pandas):   {gap2:.6f}")
assert gap1 < 1e-3 and gap2 < 1e-3, "SQL and pandas results disagree"
print("OK: SQL and pandas agree")
