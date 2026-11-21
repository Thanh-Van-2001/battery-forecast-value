#!/bin/bash
# RAM guard for the revision TSFM run: pause our own forecast shards (SIGSTOP) when available RAM < 700 MB, resume
# above 1500 MB. Only PIDs running code/revision_tsfm.py whose cwd is this directory are touched.
DIR=/mnt/data1/thanh/battery_forecast_value
cd $DIR || exit 1
paused=0
while [ ! -f results_revision/TSFM_DONE ] && [ ! -f results_revision/TSFM_FAILED ]; do
  avail=$(free -m | awk '/^Mem:/{print $7}')
  pids=$(for p in $(pgrep -u "$(id -u)" -f 'code/revision_tsfm[.]py'); do
           [ "$(readlink /proc/$p/cwd 2>/dev/null)" = "$DIR" ] && echo -n "$p "; done)
  if [ -n "$pids" ]; then
    if [ $paused -eq 0 ] && [ "$avail" -lt 700 ]; then
      kill -STOP $pids; paused=1; echo "$(date -u +%FT%TZ) avail=${avail}MB PAUSE" >> logs/mem_guard_tsfm.log
    elif [ $paused -eq 1 ] && [ "$avail" -gt 1500 ]; then
      kill -CONT $pids; paused=0; echo "$(date -u +%FT%TZ) avail=${avail}MB RESUME" >> logs/mem_guard_tsfm.log
    fi
  fi
  sleep 10
done
