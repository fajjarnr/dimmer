#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pkill -f dimmer_passthrough 2>/dev/null
case "$1" in
    1) "$SCRIPT_DIR/dimmer_passthrough" 1 & echo "Light (20% dark)" ;;
    2) "$SCRIPT_DIR/dimmer_passthrough" 2 & echo "Medium (40% dark)" ;;
    3) "$SCRIPT_DIR/dimmer_passthrough" 3 & echo "Dark (60% dark)" ;;
    4) "$SCRIPT_DIR/dimmer_passthrough" 4 & echo "Very dark (80% dark)" ;;
    5) "$SCRIPT_DIR/dimmer_passthrough" 5 & echo "Ultra (100% - hitam)" ;;
    off) echo "Dimmer off" ;;
    *) echo "Usage: $0 [1-5|off]" ;;
esac
