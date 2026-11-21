#!/bin/bash
# Post-submission exploratory run (revision kit, 20 Nov 2026): Chronos-Bolt forecasts in 6 shards, then the battery
# simulation for them. Outputs in results_revision/ only.
cd /mnt/data1/thanh/battery_forecast_value || exit 1
T=/mnt/data1/thanh/tsfm/.venv/bin/python
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
echo "$(date -u +%FT%TZ) tsfm start" >> logs/steps.log
for i in 0 1 2 3 4 5; do
  SHARD=$i/6 nice -n 19 $T code/revision_tsfm.py forecast data results_revision 2 > logs/revision_tsfm_f$i.log 2>&1 &
done
wait
ls results_revision/tsfm_bolt_shard*of6.npz | wc -l | grep -q '^6$' || { echo forecast_failed > results_revision/TSFM_FAILED; exit 1; }
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
nice -n 19 .venv/bin/python code/revision_tsfm.py simulate data results_revision 6 > logs/revision_tsfm_sim.log 2>&1 \
  && date -u > results_revision/TSFM_DONE || echo sim_failed > results_revision/TSFM_FAILED
echo "$(date -u +%FT%TZ) tsfm end" >> logs/steps.log
