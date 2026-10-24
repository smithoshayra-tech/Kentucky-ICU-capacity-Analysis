-- Weighted state-week ICU use (sum of beds in use / sum of staffed beds), then each state's peak inside a wave.
-- Wave dates are the analyst-defined windows documented in the README.
WITH state_week AS (
    SELECT state, week,
           SUM(icu_used) * 1.0 / SUM(icu_beds) AS icu_occ
    FROM hospital_week
    WHERE icu_occ IS NOT NULL
    GROUP BY state, week
)
SELECT state,
       ROUND(MAX(CASE WHEN week BETWEEN '2020-10-18' AND '2021-02-28' THEN icu_occ END), 4) AS peak_winter_2020_21,
       ROUND(MAX(CASE WHEN week BETWEEN '2021-07-25' AND '2021-11-14' THEN icu_occ END), 4) AS peak_delta_2021,
       ROUND(MAX(CASE WHEN week BETWEEN '2021-12-12' AND '2022-03-06' THEN icu_occ END), 4) AS peak_omicron_2021_22
FROM state_week
GROUP BY state
ORDER BY peak_delta_2021 DESC;
