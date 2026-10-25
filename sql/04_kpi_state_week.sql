-- KPI table: one row per state per week. Definitions are in docs/kpi_definitions.md.
-- Hospitals counted are those that reported valid ICU data in at least one week (hospitals with no ICU are left out).
-- K1-K4 come from the cleaned hospital file (hospital_week); K5 comes from the state file (state_week).
WITH ever_icu AS (
    SELECT DISTINCT hospital_pk FROM hospital_week WHERE icu_occ IS NOT NULL AND icu_beds > 0
),
icu AS (
    SELECT state, week,
           COUNT(*)                                              AS hospital_rows,
           SUM(CASE WHEN icu_occ IS NOT NULL AND icu_beds > 0 THEN 1 ELSE 0 END)           AS valid_icu_hospitals,
           SUM(CASE WHEN icu_occ IS NOT NULL AND icu_beds > 0 THEN icu_used ELSE 0 END)    AS icu_used,
           SUM(CASE WHEN icu_occ IS NOT NULL AND icu_beds > 0 THEN icu_beds ELSE 0 END)    AS icu_beds,
           SUM(CASE WHEN icu_occ >= 0.90 AND icu_beds > 0 THEN 1 ELSE 0 END)               AS strained_hospitals
    FROM hospital_week
    WHERE hospital_pk IN (SELECT hospital_pk FROM ever_icu)
    GROUP BY state, week
)
SELECT i.state,
       i.week,
       ROUND(i.icu_used * 1.0 / NULLIF(i.icu_beds, 0), 4)                     AS k1_icu_occupancy,
       i.strained_hospitals                                                    AS k2_strained_hospitals,
       ROUND(i.strained_hospitals * 1.0 / NULLIF(i.valid_icu_hospitals, 0), 4) AS k3_share_hospitals_strained,
       ROUND(i.valid_icu_hospitals * 1.0 / i.hospital_rows, 4)                 AS k4_icu_reporting_completeness,
       s.staff_short_share                                                     AS k5_critical_staffing_shortage_rate,
       i.valid_icu_hospitals
FROM icu i
LEFT JOIN state_week s ON s.state = i.state AND s.week = i.week
ORDER BY i.state, i.week;
