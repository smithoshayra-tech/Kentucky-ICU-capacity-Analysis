# KPI definitions

Six KPIs, each with one written definition. K1 to K5 are calculated in SQL (`sql/04_kpi_state_week.sql`) and re-calculated independently in pandas; `scripts/06_kpis.py` stops with an error if the two disagree. K6 is calculated in `scripts/02_analyze.py`.

All KPIs use the cleaned files, so the cleaning rules in `docs/cleaning_log.csv` apply (suppression codes removed, occupancy above 150% removed, isolated one-week spikes removed).

| # | KPI | Formula | Grain | Source | Why it matters |
|---|---|---|---|---|---|
| K1 | ICU occupancy | Adult ICU beds in use / staffed adult ICU beds, summed over hospitals with a valid value that week | State, week | Hospital file | The headline load measure |
| K2 | Strained hospitals | Number of hospitals with ICU occupancy of 90% or more | State, week | Hospital file | Counts hospitals with little room left |
| K3 | Share of hospitals strained | K2 / hospitals with a valid ICU value that week | State, week | Hospital file | Puts K2 on a comparable scale across states |
| K4 | ICU reporting completeness | Hospitals with a valid ICU value / hospitals that reported any row that week, among hospitals that ever reported ICU data | State, week | Hospital file | Tells the reader how much to trust K1 to K3 that week |
| K5 | Critical staffing shortage rate | Hospitals reporting a critical staffing shortage / hospitals answering yes or no | State, week | State file | Staffing pressure, which can tighten capacity even when beds exist |
| K6 | Strained hospitals with no nearby room | Strained Kentucky hospital-weeks where no other hospital within 60 miles was below 80% ICU use with at least 2 open beds / all strained Kentucky hospital-weeks | Kentucky, week | Hospital file plus location | Shows whether strain was local or whether neighbors had room. It measures room, not actual transfers |

## Notes
- "Valid" means the hospital reported on at least 4 of the 7 days and staffed ICU beds were above zero.
- Hospitals with no adult ICU are left out of K1 to K4.
- K5 is missing for some state-weeks in the state file; the report shows "n/a" instead of a guess.
- Thresholds (90% strained, 80% room, 60 miles, 2 beds) are analyst choices. `outputs/sensitivity.csv` shows the main result also holds at an 85% threshold.
