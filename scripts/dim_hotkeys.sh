#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$1" in
    ultra) pkill -f dimmer_passthrough; "$SCRIPT_DIR/dimmer_passthrough" 5 & ;;
    light) pkill -f dimmer_passthrough; "$SCRIPT_DIR/dimmer_passthrough" 1 & ;;
    dark) pkill -f dimmer_passthrough; "$SCRIPT_DIR/dimmer_passthrough" 3 & ;;
    off) pkill -f dimmer_passthrough ;;
esac
