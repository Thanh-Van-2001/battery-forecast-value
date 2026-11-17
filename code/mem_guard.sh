#!/bin/bash
# Pause our pipeline processes (SIGSTOP) when available RAM < 800 MB, resume above 1500 MB. Never touches other users'
# or other projects' processes: only PIDs whose command matches our scripts AND whose cwd is our directory.
DIR=/mnt/data1/thanh/battery_forecast_value
LOG=$DIR/logs/mem_guard.log
paused=0
ours() { for p in $(pgrep -u "$(id -u)" -f 'code/(prep|forecasts|simulate|analyze)[.]py'); do
           [ "$(readlink /proc/$p/cwd 2>/dev/null)" = "$DIR" ] && echo -n "$p "; done; }
while [ ! -f $DIR/results/DONE ] && [ ! -f $DIR/results/FAILED ]; do
  avail=$(free -m | awk '/^Mem:/{print $7}'); pids=$(ours)
  if [ -n "$pids" ]; then
    if [ $paused -eq 0 ] && [ "$avail" -lt 800 ]; then
      kill -STOP $pids; paused=1; echo "$(date -u +%FT%TZ) avail=${avail}MB PAUSE $pids" >> $LOG
    elif [ $paused -eq 1 ] && [ "$avail" -gt 1500 ]; then
      kill -CONT $pids; paused=0; echo "$(date -u +%FT%TZ) avail=${avail}MB RESUME" >> $LOG
    fi
  fi
  sleep 15
done
[ $paused -eq 1 ] && kill -CONT $(ours) 2>/dev/null
echo "$(date -u +%FT%TZ) guard exits" >> $LOG
