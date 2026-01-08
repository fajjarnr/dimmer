# AGENTS.md - Dimmer Brightness Control

This document provides guidance for AI coding agents working on this repository.

## Project Overview

Brightness control overlay for KDE Plasma (Wayland/XWayland) - similar to CareUEyes on Windows.
- **X11/Xlib based overlay**: Black transparent window with input passthrough
- **Python GUI sliders**: Tkinter-based brightness control interface
- **Two dimmer binaries**: 5-level (20% step) and 20-level (5% step)
- **Target OS**: Nobara Linux (Fedora-based) with KDE Plasma

## Directory Structure

```
/home/jay/Projects/dimmer/
├── dimmer_passthrough.c           # C source (5-level dimmer)
├── dimmer_passthrough             # Compiled binary (5-level, 20% step)
├── dimmer_passthrough_20lvl.c     # C source (20-level dimmer)
├── dimmer_passthrough_20lvl       # Compiled binary (20-level, 5% step)
├── dimmer_tray.py                 # System tray app (GTK3/AppIndicator)
├── dimmer-tray.desktop            # Desktop entry for autostart
├── slider_5pct.py                 # GUI slider 5% step (RECOMMENDED)
├── slider_20pct.py                # GUI slider 20% step (fast)
├── dim_control.sh                 # Command line control script
├── dim_hotkeys.sh                 # KDE hotkeys wrapper
├── README.md                      # User documentation
└── AGENTS.md                      # This file
```

## Build/Lint/Test Commands

### C Compilation

```bash
# Compile 5-level dimmer
gcc -o dimmer_passthrough dimmer_passthrough.c -lX11 -lXext

# Compile 20-level dimmer
gcc -o dimmer_passthrough_20lvl dimmer_passthrough_20lvl.c -lX11 -lXext

# Compile with warnings
gcc -Wall -Wextra -O2 -o dimmer_passthrough dimmer_passthrough.c -lX11 -lXext
```

### Shell Scripts (Bash)

```bash
# Lint with shellcheck
shellcheck dim_control.sh dim_hotkeys.sh

# Lint single file
shellcheck dim_control.sh

# Check bash syntax
bash -n dim_control.sh

# Test script (manual)
./dim_control.sh 3
```

### Python Scripts

```bash
# Lint with ruff
ruff check slider_5pct.py slider_20pct.py

# Lint single file
ruff check slider_5pct.py

# Format with ruff
ruff format slider_5pct.py

# Check syntax
python3 -m py_compile slider_5pct.py

# Run GUI slider (manual test)
./slider_5pct.py
```

### Running Tests

```bash
# Manual testing of dimmer overlay
./dimmer_passthrough 1  # Light
./dimmer_passthrough 5  # Ultra

# Test slider GUI
./slider_5pct.py &  # Run in background

# Kill all dimmer processes
pkill -f dimmer_passthrough
pkill -f slider
```

## Code Style Guidelines

### C Code Conventions

#### Header and Includes
```c
#include <X11/Xlib.h>
#include <X11/extensions/shape.h>
#include <X11/Xatom.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
```

#### Function and Variable Naming
```c
// Functions: snake_case with descriptive names
int main(int argc, char *argv[]) {
    Display *d = XOpenDisplay(NULL);
    if (!d) return 1;
    
    int s = DefaultScreen(d);
    Window root = RootWindow(d, s);
    
    // Variables: snake_case for local, UPPER_SNAKE_CASE for constants
    int level = 10;  // Default 50%
    unsigned long opacity = 0x99000000;
}
```

#### Error Handling
```c
// Always check X11 return values
Display *d = XOpenDisplay(NULL);
if (!d) return 1;

// Validate input arguments
if (level < 1) level = 1;
if (level > 20) level = 20;

// Check XShape extension availability
if (XShapeQueryExtension(d, &event_base, &error_base)) {
    Region region = XCreateRegion();
    XShapeCombineRegion(d, w, ShapeInput, 0, 0, region, ShapeSet);
    XDestroyRegion(region);
}
```

#### Memory and Resource Management
```c
// Always destroy X11 resources before exit
XDestroyWindow(d, w);
XCloseDisplay(d);

// Destroy regions after use
XDestroyRegion(region);

// Use XSync to ensure flush
XFlush(d);
XSync(d, False);
```

### Python Code Conventions

#### Header and Imports
```python
#!/usr/bin/env python3
import tkinter as tk
import subprocess
```

#### Function and Variable Naming
```python
# Functions: snake_case
def get_level_name(l):
    if l <= 4: return "Bright"
    return "Dark"

# Variables: snake_case
status = tk.StringVar(value="50% - Light")

def on_change(val):
    l = int(float(val))
    pct = l * 5
    status.set(f"{pct}% - {get_level_name(l)}")
```

#### Process Management
```python
# Kill old dimmer processes
subprocess.run(['pkill','-f','dimmer_passthrough_20lvl'], stderr=subprocess.DEVNULL)

# Start new process in background
subprocess.Popen(['./dimmer_passthrough_20lvl', str(l)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```

#### Tkinter GUI Patterns
```python
# Window setup
root = tk.Tk()
root.title("Dimmer (5% steps)")
root.geometry("350x180")
root.attributes('-topmost', True)  # Always on top

# Slider with callback
slider = tk.Scale(root, from_=1, to=20, orient='horizontal',
                  command=on_change, resolution=1)
slider.set(10)
slider.pack(fill='x', padx=20, pady=10)

# Buttons with lambda
tk.Button(root, text="50%", command=lambda: slider.set(10)).pack(side='left', padx=5)
```

### Shell Script Conventions

#### Header and Shebang
```bash
#!/bin/bash
pkill -f dimmer_passthrough 2>/dev/null
case "$1" in
    1) ./dimmer_passthrough 1 & echo "Light (20% dark)" ;;
    2) ./dimmer_passthrough 2 & echo "Medium (40% dark)" ;;
    *) echo "Usage: ./dim_control.sh [1-5|off]" ;;
esac
```

#### Process Management
```bash
# Kill processes silently
pkill -f dimmer_passthrough 2>/dev/null

# Run in background
./dimmer_passthrough 3 &
```

## Key Implementation Patterns

### X11 Overlay Window Creation
```c
// Create overlay window (no decorations, always on top)
XSetWindowAttributes attrs;
attrs.override_redirect = True;
attrs.background_pixel = BlackPixel(d, s);

Window w = XCreateWindow(
    d, root, 0, 0,
    DisplayWidth(d, s), DisplayHeight(d, s),
    0, CopyFromParent, InputOutput, CopyFromParent,
    CWOverrideRedirect | CWBackPixel, &attrs
);
```

### Window Type Configuration
```c
// Set window type to DESKTOP for background overlay
Atom window_type = XInternAtom(d, "_NET_WM_WINDOW_TYPE", False);
Atom desktop_type = XInternAtom(d, "_NET_WM_WINDOW_TYPE_DESKTOP", False);
XChangeProperty(d, w, window_type, XA_ATOM, 32, PropModeReplace,
                (unsigned char*)&desktop_type, 1);
```

### Opacity Setting
```c
// Set window opacity (ARGB format)
unsigned long opacity = 0x99000000;  // 60% opacity
Atom opacity_atom = XInternAtom(d, "_NET_WM_WINDOW_OPACITY", False);
XChangeProperty(d, w, opacity_atom, XA_CARDINAL, 32, PropModeReplace,
                (unsigned char*)&opacity, 1);
```

### Input Passthrough
```c
// Make window transparent to mouse clicks
Region region = XCreateRegion();
XShapeCombineRegion(d, w, ShapeInput, 0, 0, region, ShapeSet);
XDestroyRegion(region);
```

## Testing Guidelines

- Test dimmer on Wayland (via XWayland DISPLAY=:0)
- Verify overlay covers entire screen (check DisplayWidth/Height)
- Test input passthrough - clicks should pass through to other windows
- Verify no window decorations appear
- Test all brightness levels (1-5 or 1-20)
- Ensure smooth transitions when adjusting slider
- Test with multiple monitors (if available)

## Important Notes

- **Wayland compatibility**: Uses XWayland (DISPLAY=:0) for overlay
- **Input passthrough**: Critical for usability - window must not block clicks
- **No window manager interference**: override_redirect prevents decorations
- **Process lifecycle**: Dimmer runs for 1 hour (sleep 3600) then exits
- **Display environment**: Always use DISPLAY=:0 for XWayland compatibility
- **KDE Plasma**: Target desktop environment
- **RHEL/Fedora**: Use dnf for dependencies (libX11-devel, libXext-devel)

## User Documentation

See `README.md` for end-user instructions on running the dimmer application.
