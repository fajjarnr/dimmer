#!/usr/bin/env python3
"""
Dimmer Tray Application
A system tray application for screen brightness control.
Runs in the background and provides quick access to dimmer settings.
"""

import gi
import subprocess
import os
import signal
import sys

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIMMER_BINARY = os.path.join(SCRIPT_DIR, 'dimmer_passthrough_20lvl')

# Global reference to prevent garbage collection
app = None


class DimmerTray:
    """System tray application for dimmer control."""
    
    def __init__(self):
        self.current_level = 0  # 0 = off
        self.slider_window = None
        
        # Create the indicator
        self.indicator = AppIndicator3.Indicator.new(
            "dimmer-tray",
            "display-brightness-symbolic",  # Use system icon
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Dimmer - Screen Brightness Control")
        
        # Build the menu
        self.build_menu()
        
    def build_menu(self):
        """Build the system tray context menu."""
        self.menu = Gtk.Menu()
        
        # Header
        header = Gtk.MenuItem(label="🔆 Dimmer Control")
        header.set_sensitive(False)
        self.menu.append(header)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Quick brightness presets - using a different approach for callbacks
        item_off = Gtk.MenuItem(label="☀️  Off (No Dimming)")
        item_off.connect("activate", self.set_level_0)
        self.menu.append(item_off)
        
        item_bright = Gtk.MenuItem(label="🌤️  Bright (10%)")
        item_bright.connect("activate", self.set_level_2)
        self.menu.append(item_bright)
        
        item_light = Gtk.MenuItem(label="⛅  Light (30%)")
        item_light.connect("activate", self.set_level_6)
        self.menu.append(item_light)
        
        item_medium = Gtk.MenuItem(label="🌥️  Medium (50%)")
        item_medium.connect("activate", self.set_level_10)
        self.menu.append(item_medium)
        
        item_dark = Gtk.MenuItem(label="�  Dark (70%)")
        item_dark.connect("activate", self.set_level_14)
        self.menu.append(item_dark)
        
        item_very_dark = Gtk.MenuItem(label="🌑  Very Dark (90%)")
        item_very_dark.connect("activate", self.set_level_18)
        self.menu.append(item_very_dark)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Slider window option
        slider_item = Gtk.MenuItem(label="🎚️  Open Slider...")
        slider_item.connect("activate", self.on_open_slider)
        self.menu.append(slider_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Current status
        self.status_item = Gtk.MenuItem(label="Status: Off")
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Quit option
        quit_item = Gtk.MenuItem(label="❌  Quit")
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)
        
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
    
    # Individual level setters to avoid closure issues
    def set_level_0(self, widget):
        self.set_dimmer_level(0)
    
    def set_level_2(self, widget):
        self.set_dimmer_level(2)
    
    def set_level_6(self, widget):
        self.set_dimmer_level(6)
    
    def set_level_10(self, widget):
        self.set_dimmer_level(10)
    
    def set_level_14(self, widget):
        self.set_dimmer_level(14)
    
    def set_level_18(self, widget):
        self.set_dimmer_level(18)
    
    def set_dimmer_level(self, level):
        """Set the dimmer to specified level (0-20)."""
        print(f"[DEBUG] Setting dimmer level to {level}")
        
        # Kill any existing dimmer process
        try:
            subprocess.run(['pkill', '-f', 'dimmer_passthrough'],
                          stderr=subprocess.DEVNULL, timeout=2)
        except subprocess.TimeoutExpired:
            pass
        
        self.current_level = level
        
        if level == 0:
            self.status_item.set_label("Status: Off")
            self.indicator.set_icon_full("display-brightness-symbolic", "Dimmer Off")
            print("[DEBUG] Dimmer turned off")
        else:
            pct = level * 5
            self.status_item.set_label(f"Status: {pct}% dimmed")
            
            # Start the dimmer process
            try:
                proc = subprocess.Popen(
                    [DIMMER_BINARY, str(level)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                print(f"[DEBUG] Started dimmer with PID {proc.pid}, level {level} ({pct}%)")
            except Exception as e:
                print(f"[ERROR] Failed to start dimmer: {e}")
                return
            
            # Update icon based on level
            if level <= 6:
                self.indicator.set_icon_full("display-brightness-high-symbolic", f"Dimmer {pct}%")
            elif level <= 12:
                self.indicator.set_icon_full("display-brightness-medium-symbolic", f"Dimmer {pct}%")
            else:
                self.indicator.set_icon_full("display-brightness-low-symbolic", f"Dimmer {pct}%")
    
    def on_open_slider(self, widget):
        """Open the slider control window."""
        print("[DEBUG] Opening slider window")
        if self.slider_window is not None:
            self.slider_window.present()
            return
        
        self.slider_window = SliderWindow(self)
        self.slider_window.show_all()
    
    def on_slider_closed(self):
        """Called when slider window is closed."""
        self.slider_window = None
    
    def on_quit(self, widget):
        """Handle quit action."""
        print("[DEBUG] Quitting...")
        # Kill any dimmer process
        subprocess.run(['pkill', '-f', 'dimmer_passthrough'],
                      stderr=subprocess.DEVNULL)
        Gtk.main_quit()
    
    def run(self):
        """Run the GTK main loop."""
        # Handle SIGINT (Ctrl+C)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.on_quit, None)
        Gtk.main()


class SliderWindow(Gtk.Window):
    """Slider window for fine-grained brightness control."""
    
    def __init__(self, tray_app):
        super().__init__(title="Dimmer Control")
        self.tray_app = tray_app
        
        self.set_default_size(400, 200)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self.set_resizable(False)
        
        # Apply dark theme
        self.apply_css()
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(25)
        main_box.set_margin_end(25)
        self.add(main_box)
        
        # Title
        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>🔆 Brightness Control</span>")
        main_box.pack_start(title, False, False, 0)
        
        # Status label
        self.status_label = Gtk.Label()
        self.update_status_label()
        main_box.pack_start(self.status_label, False, False, 5)
        
        # Slider
        self.adjustment = Gtk.Adjustment(
            value=self.tray_app.current_level,
            lower=0,
            upper=20,
            step_increment=1,
            page_increment=5,
            page_size=0
        )
        
        self.slider = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=self.adjustment
        )
        self.slider.set_digits(0)
        self.slider.set_draw_value(True)
        self.slider.set_value_pos(Gtk.PositionType.RIGHT)
        
        # Add marks
        for i in range(0, 21, 5):
            self.slider.add_mark(i, Gtk.PositionType.BOTTOM, f"{i*5}%")
        
        self.slider.connect("value-changed", self.on_slider_changed)
        main_box.pack_start(self.slider, False, False, 10)
        
        # Preset buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        
        presets = [
            ("Off", 0),
            ("30%", 6),
            ("50%", 10),
            ("70%", 14),
        ]
        
        for label, level in presets:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self.on_preset_clicked, level)
            button_box.pack_start(btn, False, False, 0)
        
        main_box.pack_start(button_box, False, False, 5)
        
        # Additional buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        action_box.set_halign(Gtk.Align.END)
        
        hide_btn = Gtk.Button(label="Hide to Tray")
        hide_btn.connect("clicked", self.on_hide)
        action_box.pack_end(hide_btn, False, False, 0)
        
        main_box.pack_end(action_box, False, False, 0)
        
        # Handle window close
        self.connect("delete-event", self.on_delete)
    
    def apply_css(self):
        """Apply custom CSS styling."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background-color: #2d2d2d;
            }
            label {
                color: #ffffff;
            }
            scale {
                min-height: 30px;
            }
            scale trough {
                min-height: 8px;
                background-color: #404040;
                border-radius: 4px;
            }
            scale highlight {
                background: linear-gradient(to right, #4a90d9, #64b5f6);
                border-radius: 4px;
            }
            scale slider {
                min-width: 20px;
                min-height: 20px;
                background-color: #ffffff;
                border-radius: 50%;
            }
            button {
                padding: 8px 16px;
                background-color: #404040;
                color: #ffffff;
                border: none;
                border-radius: 6px;
            }
            button:hover {
                background-color: #505050;
            }
            button:active {
                background-color: #606060;
            }
        """)
        
        screen = self.get_screen()
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def update_status_label(self):
        """Update the status label text."""
        level = self.tray_app.current_level
        if level == 0:
            text = "No dimming (Full brightness)"
            desc = "☀️"
        else:
            pct = level * 5
            if pct <= 20:
                desc = "🌤️ Bright"
            elif pct <= 40:
                desc = "⛅ Light"
            elif pct <= 60:
                desc = "🌥️ Medium"
            elif pct <= 80:
                desc = "🌙 Dark"
            else:
                desc = "🌑 Very Dark"
            text = f"{pct}% dimmed - {desc}"
        
        self.status_label.set_markup(f"<span size='medium'>{text}</span>")
    
    def on_slider_changed(self, widget):
        """Handle slider value change."""
        level = int(self.adjustment.get_value())
        self.tray_app.set_dimmer_level(level)
        self.update_status_label()
    
    def on_preset_clicked(self, widget, level):
        """Handle preset button click."""
        self.adjustment.set_value(level)
    
    def on_hide(self, widget):
        """Hide window to tray."""
        self.hide()
        self.tray_app.on_slider_closed()
        self.destroy()
    
    def on_delete(self, widget, event):
        """Handle window close button."""
        self.tray_app.on_slider_closed()
        return False  # Allow window to be destroyed


def main():
    """Main entry point."""
    global app
    
    # Check if dimmer binary exists
    if not os.path.isfile(DIMMER_BINARY):
        print(f"Error: Dimmer binary not found at {DIMMER_BINARY}")
        print("Please compile it first with:")
        print("  gcc -o dimmer_passthrough_20lvl dimmer_passthrough_20lvl.c -lX11 -lXext")
        return 1
    
    # Check if binary is executable
    if not os.access(DIMMER_BINARY, os.X_OK):
        print(f"Error: Dimmer binary is not executable: {DIMMER_BINARY}")
        print("Please run: chmod +x dimmer_passthrough_20lvl")
        return 1
    
    print("=" * 50)
    print("Dimmer Tray started!")
    print("=" * 50)
    print(f"Binary: {DIMMER_BINARY}")
    print("Look for the brightness icon in your system tray.")
    print("Right-click the icon to access controls.")
    print("Press Ctrl+C to quit.")
    print("=" * 50)
    
    app = DimmerTray()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
