#!/bin/bash
case "$1" in
    ultra) pkill -f dimmer_passthrough; ./dimmer_passthrough 5 & ;;
    light) pkill -f dimmer_passthrough; ./dimmer_passthrough 1 & ;;
    dark) pkill -f dimmer_passthrough; ./dimmer_passthrough 3 & ;;
    off) pkill -f dimmer_passthrough ;;
esac
