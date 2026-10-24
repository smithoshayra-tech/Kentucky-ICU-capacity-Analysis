# Data dictionary

## data_clean/hospital_week_clean.csv.gz (one row per hospital per week)
| Column | Meaning |
|---|---|
| hospital_pk, ccn | HHS hospital key and 6-digit CMS certification number (join key to CMS) |
| hospital_name, city, zip, state, county, fips_code | Location fields from HHS, county from CMS |
| hospital_subtype | Short Term or Critical Access Hospitals (other types removed, step F04) |
| ownership, emergency_services, cms_rating | From CMS Hospital General Information |
| lat, lon | Parsed from the HHS geocoded address |
| ky_side | Kentucky hospitals only: Lexington-side or Louisville-side (analyst rule, step F13) |
| miles_to_nearest_hub | Straight-line miles to the assigned hub |
| collection_week | Sunday that starts the reporting week |
| inp_beds, inp_used, inp_covid | Staffed inpatient beds, beds in use, beds used by COVID patients (7-day averages) |
| icu_beds, icu_used, icu_covid | Same three measures for adult ICU |
| inp_occ, icu_occ | used / staffed beds. Blank when beds are zero, coverage under 4 days, or value above 150% |
| flag_over100 | Occupancy between 100% and 150% (kept; may be surge beds) |
| flag_spike, flag_spike_inp | Isolated one-week jump of more than 35 points that reverses next week (set to missing) |
| flag_cap_shift | One-off staffed-bed-count blip against the local 9-week median (more than 50% and 3+ beds) |
| main_ok | Row passes every check and is used in the main analysis |
| stable_reporter | Hospital has 52 or more valid ICU weeks |
| hosp_valid_icu_weeks | Count of valid ICU weeks for that hospital |

## data_clean/state_week_clean.csv (one row per state per week, 50 states)
| Column | Meaning |
|---|---|
| state, week | State and Sunday-start week |
| icu_util, inp_util | Adult ICU and inpatient bed use as a share of staffed beds (HHS state file) |
| covid_share | Share of inpatients with COVID |
| staff_short_share | Hospitals reporting a critical staffing shortage today / hospitals answering yes or no |
| staff_reporting_n | Average number of hospitals answering per day |
| days | Days of data in the week |

## outputs/ and tableau_extracts/
Each CSV is named for the table it answers (for example strain_by_state.csv, ky_vs_peers_tests.csv). tableau_extracts/ holds flat, one-grain files for building a Tableau or Power BI dashboard.

## docs/cleaning_log.csv
Every cleaning step with rows before, rows after, values affected and the reason.
