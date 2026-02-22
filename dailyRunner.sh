#!/bin/bash
# Horst Schmid
# do a first run immediately at start and then run daily once at given TARGET_HOUR 

# shellcheck disable=SC2269
TARGET_HOUR="${TARGET_HOUR%%:*}" # 4, 4:00 is converted to 4
CHECK_INTERVAL_S="${CHECK_INTERVAL_S}"
  # gut 1 Stunde Verzögerung nach dem Lauf damit sich TARGET_HOUR erst wieder einen Tag später zutrifft
if [ -z "$TARGET_HOUR" ]; then
  TARGET_HOUR=4 # set defaults, if not in environment
fi
: "${CHECK_INTERVAL_S:=300}" # short form: Parameter-Expansion with default assignment

#  export LOGLEVEL=DEBUG # optional for todo.py, overwrite value from .env

on_sigterm() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh stopped by SIGTERM (Container-Stop)"
  exit 10
  }

on_sigint() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh stopped by SIGINT (Ctrl+c)"
  exit 11
  }

trap 'on_sigterm' TERM # POSIX, BASH also possible: trap on_sigterm SIGTERM
trap 'on_sigint'  INT


# shellcheck disable=SC2164
echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh started, daily scan hour is ${TARGET_HOUR}:xx o'clock, initial run of todo.py will be started now ..."
while true; do # endless loop
  rc=-1
  while [ $rc -ne 0 ]; do # hourly loop till success
    run_hour=$(date +%H)
    python3 -u todo.py
    rc=$?
    if [ $rc -eq "0" ]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: todo.py successfully finished, going to post-sleep till next hour"
    else   
      echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: todo.py failed with $rc, will retry to run next hour ..."    
    fi  
    while [ "$(date +%H)" -eq "$run_hour" ]; do  # delay till next hour
      sleep "$CHECK_INTERVAL_S"
      # echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: now=$(date +%H), run_hour=$run_hour"
      done # delay till next hour
    done # hourly loop till success
  echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: next hour reached, going to sleep till ${TARGET_HOUR}:00"
  while [ "$(date +%H)" -ne "$TARGET_HOUR" ]; do # wait till configured hour reached
    # sleep "$CHECK_INTERVAL_S"
    sleep "1800" # 30 minutes
    # echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: further sleeping as $(date +%H) -ne $TARGET_HOUR"
    done
  echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: TARGET_HOUR reached, starting todo.py ..."
  done