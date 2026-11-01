#!/bin/bash
# Installs the Reiss outlet monitor on a Mac and schedules it every 30 minutes.
# Usage:  curl -fsSL <raw url>/mac/install.sh | bash -s -- YOUR-NTFY-TOPIC
set -e

TOPIC="$1"
DIR="$HOME/reiss-monitor"
RAW="https://raw.githubusercontent.com/issamirza111-beep/reiss-outlet-monitor/main"
LABEL="com.reiss-outlet-monitor"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ -z "$TOPIC" ]; then
  echo "Add your ntfy topic name at the end of the command, e.g. ... | bash -s -- reiss-issa-7f3k9"
  exit 1
fi

# Python 3 comes with Apple's Command Line Tools
if ! xcode-select -p >/dev/null 2>&1 || ! /usr/bin/python3 -c "print()" >/dev/null 2>&1; then
  xcode-select --install 2>/dev/null || true
  echo ""
  echo ">> A popup should ask to install Apple's Command Line Tools. Click Install,"
  echo ">> wait for it to finish (a few minutes), then paste the same command again."
  exit 1
fi

mkdir -p "$DIR" "$HOME/Library/LaunchAgents"
cd "$DIR"
echo "$TOPIC" > ntfy_topic.txt
curl -fsSL "$RAW/mac/run.sh" -o run.sh
curl -fsSL "$RAW/reiss_monitor.py" -o reiss_monitor.py
chmod +x run.sh

echo "Installing browser-like HTTP client (optional)..."
/usr/bin/python3 -m pip install --user --quiet curl_cffi >/dev/null 2>&1 \
  && echo "  done" || echo "  skipped (it will use the built-in client instead)"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$DIR/run.sh</string></array>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/monitor.log</string>
  <key>StandardErrorPath</key><string>$DIR/monitor.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo ""
echo "Installed. First check is running now — you should get a"
echo "'Reiss outlet monitor is live' notification in a minute or two."
echo "Watch it with:  tail -f ~/reiss-monitor/monitor.log"
