-- Share of weeks each hospital's adult ICU was 90% full or more, then the average across hospitals by state.
-- Same definition as scripts/02_analyze.py: stable reporters only, at least 52 valid ICU weeks, staffed ICU beds > 0.
WITH per_hospital AS (
    SELECT state,
           hospital_pk,
           COUNT(icu_occ)                                        AS valid_weeks,
           AVG(CASE WHEN icu_occ >= 0.90 THEN 1.0 ELSE 0.0 END)  AS share_ge90
    FROM hospital_week
    WHERE stable_reporter = 1
      AND icu_occ IS NOT NULL
      AND icu_beds > 0
    GROUP BY state, hospital_pk
    HAVING COUNT(icu_occ) >= 52
)
SELECT state,
       COUNT(*)                       AS hospitals,
       ROUND(AVG(share_ge90), 4)      AS mean_share_ge90
FROM per_hospital
GROUP BY state
ORDER BY mean_share_ge90 DESC;
