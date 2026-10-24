#!/usr/bin/env bash
# Rebuilds every output from the three raw files in data_raw/.
set -euo pipefail
cd "$(dirname "$0")"
for f in anag-cw7u.csv g62h-syeh.csv Hospital_General_Information.csv; do
  [ -f "data_raw/$f" ] || { echo "Missing data_raw/$f - see README, section 'Get the data'"; exit 1; }
done
python3 scripts/01_clean.py
python3 scripts/02_analyze.py
python3 scripts/03_figures.py
python3 scripts/05_sql_checks.py
# Dashboard rebuild needs dashboard/_chart.umd.js (Chart.js 4.4.1, see README). The built dashboard/index.html is already committed.
if [ -f dashboard/_chart.umd.js ]; then python3 scripts/04_build_dashboard.py; else echo "Skipping dashboard rebuild (no dashboard/_chart.umd.js)"; fi
