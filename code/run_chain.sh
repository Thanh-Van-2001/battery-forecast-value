#!/bin/bash
# Re-check the amended pipeline on 6 buildings, then run everything. Stops if the check fails.
cd /mnt/data1/thanh/battery_forecast_value || exit 1
rm -f data/prep.npz; rm -rf results_smoke data_smoke
./code/run_smoke.sh && [ -f results_smoke/DONE ] && ./code/run_all.sh
