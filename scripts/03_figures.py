"""
03_figures.py  - builds the README figures from outputs/*.csv. Needs pandas, numpy, matplotlib.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager as fm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

for p in Path("/usr/share/fonts/truetype/crosextra").glob("Carlito-*.ttf"):
    fm.fontManager.addfont(str(p))
plt.rcParams.update({
    "font.family": ["Carlito", "DejaVu Sans"], "font.size": 11,
    "axes.edgecolor": "#c9c8c2", "axes.linewidth": 0.8, "axes.labelcolor": "#52514e",
    "xtick.color": "#52514e", "ytick.color": "#52514e", "text.color": "#0b0b0b",
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "savefig.facecolor": "#fcfcfb", "axes.grid": True, "grid.color": "#e8e7e2", "grid.linewidth": 0.7,
    "axes.axisbelow": True,
})
BLUE, ORANGE, GRAY, DGRAY, LGRAY, INK, INK2 = "#2a78d6", "#eb6834", "#a9a8a2", "#6d6c67", "#dcdbd5", "#0b0b0b", "#52514e"
WAVES = {"Winter 2020-21": ("2020-10-18", "2021-02-28"), "Delta 2021": ("2021-07-25", "2021-11-14"),
         "Omicron 2021-22": ("2021-12-12", "2022-03-06")}
PEERS = ["IL", "IN", "MO", "OH", "TN", "VA", "WV"]
facts = json.load(open(OUT / "headline_facts.json"))


import textwrap


def title(fig, head, sub=None):
    wd = int(fig.get_figwidth() * 11.2)
    hw_ = textwrap.fill(head, int(fig.get_figwidth() * 8.6))
    nl = hw_.count("\n") + 1
    fig.text(0.04, 0.965, hw_, fontsize=15.5, fontweight="bold", va="top", ha="left", color=INK, linespacing=1.15)
    if sub:
        fig.text(0.04, 0.965 - (nl * 0.30 + 0.12) / fig.get_figheight(), textwrap.fill(sub, wd), fontsize=10.5, va="top",
                 ha="left", color=INK2, linespacing=1.25)


def waves(ax, label=True, ytxt=None):
    for i, (k, (a, b)) in enumerate(WAVES.items()):
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color="#eceae4", alpha=0.7, lw=0, zorder=0)
        if label and ytxt is not None:
            ax.text(pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2, ytxt, k, ha="center", va="bottom", fontsize=9, color=INK2)


def src(fig, extra=""):
    fig.text(0.04, 0.012, "Source: HHS COVID-19 Reported Patient Impact and Hospital Capacity by Facility, weekly, Aug 2020 to Apr 2024; "
             "CMS Hospital General Information. " + extra, fontsize=8.5, color="#7a7974", ha="left", va="bottom")


def pct(ax, axis="y"):
    f = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v*100:.0f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)


sw = pd.read_csv(OUT / "state_week_occupancy.csv", parse_dates=["week"])
peaks = pd.read_csv(OUT / "wave_peaks.csv")
bystate = pd.read_csv(OUT / "strain_by_state.csv")
tests = pd.read_csv(OUT / "ky_vs_peers_tests.csv")
kside = pd.read_csv(OUT / "ky_side_week.csv", parse_dates=["week"])
hw = pd.read_csv(OUT / "ky_headroom_week.csv", parse_dates=["week"])
size = pd.read_csv(OUT / "strain_by_icu_size.csv")
lag = pd.read_csv(OUT / "staffing_lag_corr.csv")
fc = pd.read_csv(OUT / "forecast_ky_icu.csv", parse_dates=["week_origin"])
log = pd.read_csv(ROOT / "docs" / "cleaning_log.csv")

# ---------------- Figure 1: ICU occupancy over time -------------------------------------
ky = sw[sw.state == "KY"].set_index("week")["icu_occ"]
pe = sw[sw.state.isin(PEERS)].pivot(index="week", columns="state", values="icu_occ")
fig, ax = plt.subplots(figsize=(11, 5.6))
fig.subplots_adjust(left=0.07, right=0.97, top=0.77, bottom=0.12)
waves(ax, True, 1.015)
ax.fill_between(pe.index, pe.min(axis=1), pe.max(axis=1), color=LGRAY, alpha=0.9, lw=0, label="Range of the 7 border states")
ax.plot(pe.index, pe.median(axis=1), color=DGRAY, lw=1.6, label="Border-state median")
ax.plot(ky.index, ky.values, color=BLUE, lw=2.2, label="Kentucky")
ax.axhline(0.90, color=INK2, lw=0.9, ls=(0, (4, 3)))
ax.text(pd.Timestamp("2024-04-21"), 0.905, "90% full", ha="right", va="bottom", fontsize=9, color=INK2)
ax.set_ylim(0.35, 1.05)
pct(ax)
ax.set_ylabel("Adult ICU beds in use, share of staffed beds")
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.legend(loc="lower left", frameon=False, ncol=3, fontsize=10)
pk = peaks[peaks.state == "KY"].set_index("wave")
title(fig, f"Kentucky's ICUs ran hotter than every border state in both the Delta and Omicron waves",
      f"Kentucky peaked at {pk.loc['Delta 2021','peak_icu_occ']*100:.0f}% in Delta and {pk.loc['Omicron 2021-22','peak_icu_occ']*100:.0f}% in Omicron. Weekly, all reporting hospitals combined.")
src(fig)
fig.savefig(FIG / "01_icu_occupancy_ky_vs_peers.png", dpi=170)
plt.close(fig)

# ---------------- Figure 2: share of weeks at 90%+ by state -----------------------------
b = bystate.sort_values("mean_share_ge90")
fig, ax = plt.subplots(figsize=(10, 5.2))
fig.subplots_adjust(left=0.10, right=0.95, top=0.77, bottom=0.13)
cols = [BLUE if s == "KY" else GRAY for s in b.state]
ax.barh([f"{a}  (n={n})" for a, n in zip(b.state, b.n)], b.mean_share_ge90, color=cols, height=0.62)
ax.errorbar(b.mean_share_ge90, [f"{a}  (n={n})" for a, n in zip(b.state, b.n)], xerr=[b.mean_share_ge90 - b.ci_lo, b.ci_hi - b.mean_share_ge90], fmt="none", ecolor=INK2, elinewidth=1, capsize=3)
for y_, (m, n) in enumerate(zip(b.mean_share_ge90, b.n)):
    ax.text(0.005, y_, f"{m*100:.0f}%", va="center", ha="left", fontsize=10, color="white", fontweight="bold")
pct(ax, "x")
ax.set_xlim(0, 0.52)
ax.set_ylim(-0.6, len(b) - 0.4)
ax.set_xlabel("Share of weeks a hospital's adult ICU was 90% full or more (average across hospitals, bars show 95% interval)")
ax.grid(axis="y", visible=False)
t = tests[(tests.comparison == "Kentucky minus border states") & (tests.metric == "share_ge90")].iloc[0]
title(fig, "Kentucky hospitals spent about a third of weeks at 90%+ ICU use, nearly twice the border-state rate",
      f"Kentucky {t.ky_mean*100:.0f}% vs border states {t.peers_mean*100:.0f}% of hospital-weeks. Missouri and West Virginia look like Kentucky; Illinois, Virginia, Indiana and Ohio do not.")
src(fig)
fig.savefig(FIG / "02_share_of_weeks_90pct_by_state.png", dpi=170)
plt.close(fig)

# ---------------- Figure 3: by wave --------------------------------------------------------
w = tests[tests.metric == "share_ge90_in_wave"].copy()
fig, ax = plt.subplots(figsize=(10, 5.2))
fig.subplots_adjust(left=0.08, right=0.97, top=0.77, bottom=0.12)
x = np.arange(len(w))
bw = 0.34
ax.bar(x - bw / 2 - 0.01, w.ky_mean, bw, color=BLUE, label="Kentucky hospitals")
ax.bar(x + bw / 2 + 0.01, w.peers_mean, bw, color=GRAY, label="Border-state hospitals")
for i, r in enumerate(w.itertuples()):
    ax.text(i - bw / 2 - 0.01, r.ky_mean + 0.02, f"{r.ky_mean*100:.0f}%", ha="center", fontsize=10, color=INK)
    ax.text(i + bw / 2 + 0.01, r.peers_mean + 0.02, f"{r.peers_mean*100:.0f}%", ha="center", fontsize=10, color=INK)
ax.set_xticks(x)
ax.set_xticklabels([f"{c}\n" + ("gap not clearly real" if (lo < 0 < hi) else f"gap {d*100:+.0f} points")
                    for c, lo, hi, d in zip(w.comparison, w.ci_lo, w.ci_hi, w["diff"])])
ax.tick_params(axis="x", pad=2)
pct(ax)
ax.set_ylim(0, 0.8)
ax.set_ylabel("Share of weeks at 90%+ ICU use inside each wave")
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, loc="upper left")
title(fig, "The Kentucky gap opens in Delta and Omicron, not in the winter 2020-21 wave",
      "Average across hospitals that reported at least 8 weeks in the wave. In winter 2020-21 the Kentucky and border-state results are statistically indistinguishable.")
src(fig)
fig.savefig(FIG / "03_strain_by_wave.png", dpi=170)
plt.close(fig)

# ---------------- Figure 4: Lexington-side vs Louisville-side ---------------------------
fig, ax = plt.subplots(figsize=(11, 5.4))
fig.subplots_adjust(left=0.07, right=0.97, top=0.77, bottom=0.12)
waves(ax, True, 1.015)
for side, c in [("Lexington-side", BLUE), ("Louisville-side", ORANGE)]:
    d = kside[kside.ky_side == side]
    ax.plot(d.week, d.icu_occ, color=c, lw=2, label=f"{side} hospitals")
ax.axhline(0.90, color=INK2, lw=0.9, ls=(0, (4, 3)))
ax.set_ylim(0.35, 1.05)
pct(ax)
ax.set_ylabel("Adult ICU beds in use, share of staffed beds")
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.legend(loc="lower left", frameon=False, ncol=2)
title(fig, "Both sides of Kentucky surged together, so neither had much slack to lend the other",
      f"Weekly correlation between the two sides is {facts['ky_side_xcorr_at_0']:.2f}. Side = nearest of Lexington or Louisville (my assumption, not the RMOCC boundary).")
src(fig)
fig.savefig(FIG / "04_lexington_vs_louisville_side.png", dpi=170)
plt.close(fig)

# ---------------- Figure 5: headroom ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 5.4))
fig.subplots_adjust(left=0.07, right=0.97, top=0.77, bottom=0.12)
waves(ax, True, 52)
ax.bar(hw.week, hw.strained, width=5.5, color="#9ec5f4", label="Kentucky hospitals at 90%+ ICU use")
ax.bar(hw.week, hw.stranded, width=5.5, color=ORANGE, label="...with fewer than 2 open ICU beds at any hospital within 60 miles under 80% full")
ax.set_ylim(0, 56)
ax.set_ylabel("Hospitals in the week")
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.legend(loc="upper right", frameon=False, fontsize=10)
hv = pd.read_csv(OUT / "ky_headroom_by_wave.csv").set_index("wave")
title(fig, f"In Delta and Omicron, {hv.loc['Omicron 2021-22','stranded_share']*100:.0f} to {hv.loc['Delta 2021','stranded_share']*100:.0f}% of strained hospital-weeks had no nearby ICU beds to share",
      f"In winter 2020-21 only {hv.loc['Winter 2020-21','stranded_share']*100:.0f}% did. This measures open beds nearby, not transfers that actually happened (the data has no transfers).")
src(fig, "Distance is straight-line miles between hospital geocodes.")
fig.savefig(FIG / "05_nearby_headroom.png", dpi=170)
plt.close(fig)

# ---------------- Figure 6: ICU size ---------------------------------------------------------
order = ["Small: 8 beds or fewer", "Medium: 9-20", "Large: over 20"]
fig, ax = plt.subplots(figsize=(10, 5.2))
fig.subplots_adjust(left=0.08, right=0.97, top=0.77, bottom=0.12)
x = np.arange(3)
for off, g, c, lab in [(-0.18, "Kentucky", BLUE, "Kentucky"), (0.18, "Border states", GRAY, "Border states")]:
    d = size[size.group == g].set_index("icu_size").loc[order]
    ax.bar(x + off, d.mean_share_ge90, 0.34, color=c, label=lab)
    for i, (v, n) in enumerate(zip(d.mean_share_ge90, d.n)):
        ax.text(i + off, v + 0.015, f"{v*100:.0f}%", ha="center", fontsize=10)
        ax.text(i + off, 0.012, f"n={n}", ha="center", fontsize=8.5, color="white" if c == BLUE else INK)
ax.set_xticks(x)
ax.set_xticklabels(order)
pct(ax)
ax.set_ylim(0, 0.55)
ax.set_ylabel("Share of weeks at 90%+ ICU use")
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, loc="upper left")
title(fig, "In Kentucky the largest ICUs sat at 90%+ most often; border-state ICUs show no size pattern",
      "Hospitals grouped by median staffed adult ICU beds. Small samples in Kentucky (15 to 20 hospitals per group), so read the pattern, not the exact percentages.")
src(fig)
fig.savefig(FIG / "06_icu_size.png", dpi=170)
plt.close(fig)

# ---------------- Figure 7: staffing ---------------------------------------------------------
stf = pd.read_csv(ROOT / "tableau_extracts" / "state_week_staffing.csv", parse_dates=["week"])
kys = stf[stf.state == "KY"].set_index("week")["staff_short_share"].rolling(2, min_periods=1).mean()
pes = stf[stf.state.isin(PEERS)].pivot(index="week", columns="state", values="staff_short_share").median(axis=1).rolling(2, min_periods=1).mean()
fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [1, 1]})
fig.subplots_adjust(left=0.07, right=0.97, top=0.82, bottom=0.08, hspace=0.12)
for a in (a1, a2):
    waves(a, False)
a1.plot(ky.index, ky.values, color=BLUE, lw=2.2)
a1.axhline(0.90, color=INK2, lw=0.9, ls=(0, (4, 3)))
a1.set_ylim(0.35, 1.05)
pct(a1)
a1.set_ylabel("Kentucky adult ICU use")
a2.plot(kys.index, kys.values, color=BLUE, lw=2.2, label="Kentucky")
a2.plot(pes.index, pes.values, color=DGRAY, lw=1.6, label="Border-state median")
pct(a2)
a2.set_ylim(0, 0.7)
a2.set_ylabel("Hospitals reporting a critical staffing shortage")
a2.legend(frameon=False, loc="upper right")
a2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
a2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
title(fig, "Staffing shortages rose and fell with ICU strain, and Kentucky's peak was well above a typical state's",
      f"Pooled across the 8 states the two move together (correlation {facts['staffing_corr_lag0']:.2f}), but the data cannot tell which leads the other. Kentucky peaked at {facts['staff_peak_share_ky']*100:.0f}% of reporting hospitals vs a typical state peak of {facts['staff_peak_share_national_median_of_states']*100:.0f}%.")
src(fig, "Staffing from the HHS state-level daily file, averaged to weeks.")
fig.savefig(FIG / "07_staffing_vs_icu.png", dpi=170)
plt.close(fig)

# ---------------- Figure 8: forecast ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(9.5, 5.2))
fig.subplots_adjust(left=0.09, right=0.97, top=0.77, bottom=0.12)
vals = [[facts["forecast_mae_naive_pts"], facts["forecast_mae_model_pts"]],
        [facts["forecast_mae_naive_surge_pts"], facts["forecast_mae_model_surge_pts"]]]
x = np.arange(2)
ax.bar(x - 0.18, [vals[0][0], vals[1][0]], 0.34, color=GRAY, label="Same as last week")
ax.bar(x + 0.18, [vals[0][1], vals[1][1]], 0.34, color=BLUE, label="Simple regression on recent changes")
for i in range(2):
    ax.text(i - 0.18, vals[i][0] + 0.04, f"{vals[i][0]:.2f}", ha="center")
    ax.text(i + 0.18, vals[i][1] + 0.04, f"{vals[i][1]:.2f}", ha="center")
ax.set_xticks(x)
ax.set_xticklabels([f"All {facts['forecast_n_weeks']} test weeks", f"{facts['forecast_surge_weeks']} weeks at 85%+ ICU use"])
ax.set_ylabel("Average miss, in percentage points")
ax.set_ylim(0, 2.3)
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, loc="upper left")
title(fig, "A simple model did not beat 'same as last week' for next-week ICU use",
      "Rolling one-week-ahead test on Kentucky, each forecast made using only earlier data. Reported anyway: the honest result is that this series is hard to improve on.")
src(fig)
fig.savefig(FIG / "08_forecast_test.png", dpi=170)
plt.close(fig)

# ---------------- Figure 9: what cleaning changed ----------------------------------------
c = log[(log.values_affected > 0)].copy()
c = c[c.step.str.startswith("F")]
short = {"F03": "Suppression code -999999 set to missing", "F04": "Long-term and children's hospitals out of scope",
         "F05": "Fewer than 4 reporting days", "F08": "Outlier flags raised", "F09": "Isolated spikes removed",
         "F10": "Weeks before ICU reporting stabilized", "F11": "Hospital-weeks from short-history hospitals marked",
         "F12": "Rows with no CMS match", "F13": "Kentucky hospitals assigned a side"}
c["label"] = c.step.map(short)
c = c.dropna(subset=["label"]).sort_values("values_affected")
fig, ax = plt.subplots(figsize=(10.5, 5.2))
fig.subplots_adjust(left=0.38, right=0.95, top=0.77, bottom=0.12)
ax.barh(c.label, c.values_affected, color=[ORANGE if s == "F09" else "#9ec5f4" for s in c.step], height=0.62)
for y_, v in enumerate(c.values_affected):
    ax.text(v + 1200, y_, f"{v:,}", va="center", fontsize=10)
ax.set_xlim(0, c.values_affected.max() * 1.15)
ax.grid(axis="y", visible=False)
ax.set_xlabel("Values or rows affected")
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
title(fig, "Most cleaning was about suppressed values and scope, and only 46 rows were removed as spikes",
      "Every step, with the reason for it, is in docs/cleaning_log.csv.")
src(fig)
fig.savefig(FIG / "09_cleaning_steps.png", dpi=170)
plt.close(fig)
print(sorted(p.name for p in FIG.glob("*.png")))
