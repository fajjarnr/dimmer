#!/bin/bash
echo "Dimmer Quickstart"
echo "================="
echo ""
echo "Pilih mode:"
echo "1. GUI 20% step (cepat)"
echo "2. GUI 5% step (halus - RECOMMENDED)"
echo "3. Dim off"
echo ""
read -p "Pilih [1-3]: " choice

case $choice in
    1) ./slider_20pct.py & ;;
    2) ./slider_5pct.py & ;;
    3) pkill -f dimmer_passthrough; pkill -f slider; echo "Dimmer off" ;;
    *) echo "Invalid" ;;
esac
