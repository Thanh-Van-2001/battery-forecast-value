#!/bin/bash
# Full pipeline on titan (tmux "=thanh_battery", nice 19, 8 workers). Each step writes logs/<step>.log.
cd /mnt/data1/thanh/battery_forecast_value || exit 1
P=.venv/bin/python
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p results logs; rm -f results/FAILED results/DONE
run() { echo "$(date -u +%FT%TZ) start $1" >> logs/steps.log; shift; nice -n 19 "$@" || { echo "$*" >> results/FAILED; exit 1; }; }
run prep $P code/prep.py data > logs/prep.log 2>&1
run forecasts $P code/forecasts.py data 8 > logs/forecasts.log 2>&1
run sim_base $P code/simulate.py data results/bills_base.csv 8 0.10 20 > logs/sim_base.log 2>&1
run analyze $P code/analyze.py data results > logs/analyze.log 2>&1
for cfg in "0.05 20 b05" "0.20 20 b20" "0.10 10 dc10" "0.10 30 dc30"; do
  set -- $cfg
  run sim_$3 $P code/simulate.py data results/bills_$3.csv 8 $1 $2 > logs/sim_$3.log 2>&1
done
run analyze_all $P code/analyze.py data results > logs/analyze_all.log 2>&1
date -u > results/DONE
