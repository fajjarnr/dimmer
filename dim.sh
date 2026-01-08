#!/bin/bash
pkill dimmer 2>/dev/null
pkill dimmer_passthrough 2>/dev/null
pkill dimmer_x11 2>/dev/null

case "$1" in
    light) DISPLAY=:0 /tmp/dimmer_passthrough 1 & echo "Light (20% dark) - clickable" ;;
    medium) DISPLAY=:0 /tmp/dimmer_passthrough 2 & echo "Medium (30% dark) - clickable" ;;
    dark) DISPLAY=:0 /tmp/dimmer_passthrough 3 & echo "Dark (40% dark) - clickable" ;;
    very) DISPLAY=:0 /tmp/dimmer_passthrough 4 & echo "Very dark (60% dark) - clickable" ;;
    ultra) DISPLAY=:0 /tmp/dimmer_passthrough 5 & echo "Ultra dark (80% dark) - clickable" ;;
    off) echo "Dimmer off - klik tembus" ;;
    *) echo "Usage: dim.sh [light|medium|dark|very|ultra|off]" ;;
esac
