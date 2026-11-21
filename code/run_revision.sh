#!/bin/bash
# Post-submission exploratory run (revision kit, 20 Nov 2026) on titan; outputs in results_revision/, nothing else touched.
cd /mnt/data1/thanh/battery_forecast_value || exit 1
P=.venv/bin/python
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p results_revision logs; rm -f results_revision/FAILED results_revision/DONE
echo "$(date -u +%FT%TZ) revision start" >> logs/steps.log
# RAM guard: pause our workers when available memory < 800 MB, resume above 1500 MB (only our PIDs in this directory)
( while [ ! -f results_revision/DONE ] && [ ! -f results_revision/FAILED ]; do
    avail=$(free -m | awk '/^Mem:/{print $7}')
    pids=$(for p in $(pgrep -u "$(id -u)" -f 'code/revision_explore[.]py'); do
             [ "$(readlink /proc/$p/cwd 2>/dev/null)" = "$PWD" ] && echo -n "$p "; done)
    if [ -n "$pids" ]; then
      if [ "$avail" -lt 800 ]; then kill -STOP $pids; echo "$(date -u +%FT%TZ) avail=${avail}MB PAUSE" >> logs/mem_guard_rev.log
      elif [ "$avail" -gt 1500 ]; then kill -CONT $pids 2>/dev/null; fi
    fi
    sleep 15
  done ) &
nice -n 19 $P code/revision_explore.py data results_revision "${1:-6}" > logs/revision_explore.log 2>&1 \
  && date -u > results_revision/DONE || { echo failed > results_revision/FAILED; }
echo "$(date -u +%FT%TZ) revision end" >> logs/steps.log
