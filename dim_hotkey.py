#!/usr/bin/env python3
from Xlib import X, display
import subprocess
import os

def set_dimmer(level):
    subprocess.run(['pkill', '-f', 'dimmer_passthrough'], stderr=subprocess.DEVNULL)
    env = os.environ.copy()
    env['DISPLAY'] = ':0'
    subprocess.Popen(['/tmp/dimmer_passthrough', str(level)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Dimmer level {level}")

def main():
    d = display.Display()
    root = d.screen().root
    
    # Keycodes
    F3 = 0xFF70
    F4 = 0xFF71
    ESC = 0xFF1B
    
    # Grab keys dengan 0 sebagai modifier
    root.grab_key(F3, 0, True, X.GrabModeAsync, X.GrabModeAsync)
    root.grab_key(F4, 0, True, X.GrabModeAsync, X.GrabModeAsync)
    root.grab_key(ESC, 0, True, X.GrabModeAsync, X.GrabModeAsync)
    
    print("=== Dimmer Hotkeys ===")
    print("F3 = Ultra (hitam)")
    print("F4 = Light (terang)")
    print("ESC = Exit")
    
    while True:
        event = d.next_event()
        if event.type == X.KeyPress:
            keycode = event.detail
            if keycode == F3:
                set_dimmer(5)
            elif keycode == F4:
                set_dimmer(1)
            elif keycode == ESC:
                subprocess.run(['pkill', '-f', 'dimmer_passthrough'], stderr=subprocess.DEVNULL)
                break

if __name__ == "__main__":
    main()
