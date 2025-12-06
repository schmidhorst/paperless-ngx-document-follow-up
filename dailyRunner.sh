#!/bin/bash

# shellcheck disable=SC2269
TARGET_HOUR="${TARGET_HOUR}"
CHECK_INTERVAL_S="${CHECK_INTERVAL_S}"
  # gut 1 Stunde Verzögerung nach dem Lauf damit sich TARGET_HOUR erst wieder einen Tag später zutrifft
if [ -z "$TARGET_HOUR" ]; then
  TARGET_HOUR=4 # set defaults, if not in environment
fi
: "${CHECK_INTERVAL_S:=300}" # short form: Parameter-Expansion with assignment

# shellcheck disable=SC2164
echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh started, daily hour is ${TARGET_HOUR}:xx o'clock"
while true; do
  run_hour=$(date +%H)
  python3 -u todo.py
  rc=$?
  echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: todo.py finished with $rc, going to post-sleep till next hour"
  while [ "$(date +%H)" -eq "$run_hour" ]; do  # not again in that hour
    sleep "$CHECK_INTERVAL_S"
    done
  while [ "$(date +%H)" -ne "$TARGET_HOUR" ]; do # wait till configured hour reached
    sleep "$CHECK_INTERVAL_S"
    done
  echo "$(date '+%Y-%m-%d %H:%M:%S') - dailyRunner.sh: TARGET_HOUR reached, starting todo.py ..."
  done