#!/bin/bash
# Only run the wrapped command if "now" (IST) falls inside [START, END) on a weekday.
# Used so a reboot at any hour self-heals correctly: inside the window it starts the loop,
# outside it exits 0 (not a failure) and the next scheduled timer start handles it normally.
START="$1"; END="$2"; shift 2
dow=$(date +%u)   # 1=Mon .. 7=Sun
now=$(date +%H:%M)
if [ "$dow" -ge 6 ]; then echo "weekend, not starting"; exit 0; fi
if [[ "$now" < "$START" || "$now" > "$END" ]]; then echo "outside $START-$END (now $now), not starting"; exit 0; fi
exec "$@"
