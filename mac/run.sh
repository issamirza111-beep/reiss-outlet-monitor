#!/bin/bash
# Runs one outlet check. launchd calls this every 30 minutes.
# Before each check it reads control.txt and the latest script from GitHub,
# so you can pause it or change settings from your phone.

DIR="$HOME/reiss-monitor"
RAW="https://raw.githubusercontent.com/issamirza111-beep/reiss-outlet-monitor/main"
cd "$DIR" || exit 1
echo "---- $(date) ----"

# Remote on/off switch (control.txt in the GitHub repo: "on" or "off")
state=$(curl -fsS --max-time 20 "$RAW/control.txt?t=$(date +%s)" 2>/dev/null | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
if [ "$state" = "off" ]; then
  echo "Paused (control.txt says off)"
  exit 0
fi

# Pick up any settings/script changes pushed to GitHub
if curl -fsS --max-time 30 "$RAW/reiss_monitor.py?t=$(date +%s)" -o reiss_monitor.py.new 2>/dev/null \
   && /usr/bin/python3 -m py_compile reiss_monitor.py.new 2>/dev/null; then
  mv reiss_monitor.py.new reiss_monitor.py
else
  rm -f reiss_monitor.py.new
fi

export NTFY_TOPIC="$(cat "$DIR/ntfy_topic.txt")"
/usr/bin/python3 reiss_monitor.py

# Keep the log small
tail -n 2000 "$DIR/monitor.log" > "$DIR/monitor.log.tmp" 2>/dev/null && mv "$DIR/monitor.log.tmp" "$DIR/monitor.log"
