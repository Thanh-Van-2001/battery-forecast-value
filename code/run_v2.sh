#!/bin/bash
# Amendment 3 (v2): corrected simulation on the same prep.npz; v1 kept in results_v1/ and data/forecasts_v1.npz.
cd /mnt/data1/thanh/battery_forecast_value || exit 1
P=.venv/bin/python
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p results logs; rm -f results/FAILED results/DONE results/bills_*.csv results/results.json
run() { echo "$(date -u +%FT%TZ) v2 start $1" >> logs/steps.log; shift; nice -n 19 "$@" || { echo "$*" >> results/FAILED; exit 1; }; }
run forecasts $P code/forecasts.py data 6 > logs/v2_forecasts.log 2>&1
run sim_base $P code/simulate.py data results/bills_base.csv 6 0.10 20 > logs/v2_sim_base.log 2>&1
run analyze $P code/analyze.py data results > logs/v2_analyze.log 2>&1
run exploratory $P code/exploratory.py data results > logs/v2_exploratory.log 2>&1
run facts $P code/facts.py data results/facts.json > logs/v2_facts.log 2>&1
for cfg in "0.05 20 b05" "0.20 20 b20" "0.10 10 dc10" "0.10 30 dc30"; do
  set -- $cfg
  run sim_$3 $P code/simulate.py data results/bills_$3.csv 6 $1 $2 > logs/v2_sim_$3.log 2>&1
done
run analyze_all $P code/analyze.py data results > logs/v2_analyze_all.log 2>&1
date -u > results/DONE
