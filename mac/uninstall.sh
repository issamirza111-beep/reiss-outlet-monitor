#!/bin/bash
# Removes the Reiss outlet monitor from this Mac.
LABEL="com.reiss-outlet-monitor"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$HOME/reiss-monitor"
echo "Reiss outlet monitor removed."
