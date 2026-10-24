-- How many hospitals report a valid adult ICU number each quarter (a data-quality view, not a result).
SELECT SUBSTR(week, 1, 4) || '-Q' || ((CAST(SUBSTR(week, 6, 2) AS INTEGER) + 2) / 3) AS quarter,
       COUNT(DISTINCT hospital_pk)                                                   AS hospitals_in_file,
       COUNT(DISTINCT CASE WHEN icu_occ IS NOT NULL THEN hospital_pk END)            AS hospitals_with_valid_icu
FROM hospital_week
GROUP BY quarter
ORDER BY quarter;
