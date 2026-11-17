#!/bin/bash
# Pipeline check on 6 buildings (outputs in results_smoke/, forecasts_smoke kept apart from the real run).
cd /mnt/data1/thanh/battery_forecast_value || exit 1
P=.venv/bin/python
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p results_smoke logs
[ -f data/prep.npz ] || nice -n 19 $P code/prep.py data > logs/prep.log 2>&1 || { echo prep >> results_smoke/FAILED; exit 1; }
mkdir -p data_smoke && ln -sf ../data/prep.npz data_smoke/prep.npz
SMOKE=6 nice -n 19 $P code/forecasts.py data_smoke 4 > logs/smoke_forecasts.log 2>&1 || { echo forecasts >> results_smoke/FAILED; exit 1; }
nice -n 19 $P code/simulate.py data_smoke results_smoke/bills_base.csv 4 0.10 20 > logs/smoke_sim.log 2>&1 || { echo sim >> results_smoke/FAILED; exit 1; }
nice -n 19 $P code/analyze.py data_smoke results_smoke > logs/smoke_analyze.log 2>&1 || { echo analyze >> results_smoke/FAILED; exit 1; }
date -u > results_smoke/DONE
