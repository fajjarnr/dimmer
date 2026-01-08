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
import json

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, AppIndicator3, GLib, Notify

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Binary is in ../bin relative to this script in src/
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DIMMER_BINARY = os.path.join(PROJECT_ROOT, 'bin', 'dimmer_passthrough')

# Config file path
CONFIG_DIR = os.path.expanduser('~/.config/dimmer')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# Global reference to prevent garbage collection
app = None

# Initialize notification system
Notify.init("Dimmer")

# Level descriptions for 5-level system (20% steps)
LEVEL_NAMES = {
    0: "Off",
    1: "Light (20%)",
    2: "Medium (40%)",
    3: "Dark (60%)",
    4: "Very Dark (80%)",
    5: "Ultra (100%)"
}

# Warm filter levels (color temperature)
WARM_NAMES = {
    0: "Off (6500K)",
    1: "Warm 1 (5500K)",
    2: "Warm 2 (4500K)",
    3: "Warm 3 (3500K)",
    4: "Warm 4 (2700K)",
    5: "Candle (2000K)"
}

# KDE Night Light temperatures (Kelvin)
WARM_TEMPS = {
    0: 6500,  # Neutral (off)
    1: 5500,  # Slight warm
    2: 4500,  # Warm
    3: 3500,  # Warmer
    4: 2700,  # Very warm
    5: 2000,  # Candle light
}

# Preset profiles: (dimmer_level, warm_level)
PROFILES = {
    "gaming": (0, 1, "🎮 Gaming", "Full brightness, slight warm"),
    "work": (1, 2, "💼 Work", "Light dim, moderate warm"),
    "reading": (2, 3, "📖 Reading", "Medium dim, warm"),
    "movie": (2, 0, "🎬 Movie", "Medium dim, neutral colors"),
    "night": (3, 4, "🌙 Night", "Dark, very warm"),
}

# Break reminder interval (in minutes)
BREAK_INTERVAL_MINUTES = 20


class DimmerTray:
    """System tray application for dimmer control."""
    
    def __init__(self):
        self.current_level = 0  # 0 = off, 1-5 = dimmer levels
        self.warm_level = 0     # 0 = off, 1-5 = warm filter levels
        self.slider_window = None
        self.notify_enabled = True  # Show notifications for hotkey changes
        
        # Break reminder
        self.break_enabled = False
        self.break_timer_id = None
        
        # Load saved settings from config
        saved_level, saved_warm, saved_break = self.load_config()
        self.break_enabled = saved_break
        
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
        
        # Apply saved settings (after menu is built so status_item exists)
        if saved_level > 0:
            print(f"[INFO] Restoring saved dimmer level: {saved_level}")
            GLib.idle_add(lambda: self.set_dimmer_level(saved_level, notify=False))
        if saved_warm > 0:
            print(f"[INFO] Restoring saved warm level: {saved_warm}")
            GLib.idle_add(lambda: self.set_warm_level(saved_warm, notify=False))
        
        # Start break reminder if enabled
        if self.break_enabled:
            self.start_break_timer()
    
    def load_config(self):
        """Load configuration from file."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    return (
                        config.get('level', 0),
                        config.get('warm', 0),
                        config.get('break_enabled', False)
                    )
        except Exception as e:
            print(f"[WARN] Failed to load config: {e}")
        return 0, 0, False
    
    def save_config(self):
        """Save current settings to config file."""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump({
                    'level': self.current_level,
                    'warm': self.warm_level,
                    'break_enabled': self.break_enabled
                }, f)
        except Exception as e:
            print(f"[WARN] Failed to save config: {e}")
    
    def show_notification(self, title, message, icon="display-brightness-symbolic"):
        """Show a desktop notification."""
        if not self.notify_enabled:
            return
        try:
            notification = Notify.Notification.new(title, message, icon)
            notification.set_timeout(1500)  # 1.5 seconds
            notification.show()
        except Exception as e:
            print(f"[WARN] Notification failed: {e}")
    
    # ========== BREAK REMINDER ==========
    def start_break_timer(self):
        """Start the break reminder timer."""
        if self.break_timer_id:
            GLib.source_remove(self.break_timer_id)
        
        interval_ms = BREAK_INTERVAL_MINUTES * 60 * 1000
        self.break_timer_id = GLib.timeout_add(interval_ms, self.on_break_reminder)
        print(f"[INFO] Break reminder started ({BREAK_INTERVAL_MINUTES} min interval)")
    
    def stop_break_timer(self):
        """Stop the break reminder timer."""
        if self.break_timer_id:
            GLib.source_remove(self.break_timer_id)
            self.break_timer_id = None
        print("[INFO] Break reminder stopped")
    
    def on_break_reminder(self):
        """Called when break reminder triggers."""
        # Show notification
        notification = Notify.Notification.new(
            "👀 Eye Break Reminder",
            "Time to rest your eyes!\nLook at something 20 feet (6m) away for 20 seconds.",
            "dialog-information"
        )
        notification.set_timeout(10000)  # 10 seconds
        notification.set_urgency(2)  # Critical
        notification.show()
        print("[INFO] Break reminder notification shown")
        return True  # Return True to keep timer running
    
    def toggle_break_reminder(self, widget):
        """Toggle break reminder on/off."""
        if isinstance(widget, Gtk.CheckMenuItem):
            self.break_enabled = widget.get_active()
        else:
            self.break_enabled = not self.break_enabled
        
        if self.break_enabled:
            self.start_break_timer()
            self.show_notification("⏰ Break Reminder", f"Enabled - every {BREAK_INTERVAL_MINUTES} min")
        else:
            self.stop_break_timer()
            self.show_notification("⏰ Break Reminder", "Disabled")
        
        self.save_config()
    
    # ========== PROFILES ==========
    def apply_profile(self, profile_name):
        """Apply a preset profile."""
        if profile_name not in PROFILES:
            return
        
        dim_level, warm_level, label, desc = PROFILES[profile_name]
        self.set_dimmer_level(dim_level, notify=False)
        self.set_warm_level(warm_level, notify=False)
        self.show_notification(f"{label} Profile", desc)
        
    def build_menu(self):
        """Build the system tray context menu."""
        self.menu = Gtk.Menu()
        
        # Header
        header = Gtk.MenuItem(label="🔆 Dimmer Control")
        header.set_sensitive(False)
        self.menu.append(header)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Quick brightness presets - 5 levels with 20% steps
        item_off = Gtk.MenuItem(label="☀️  Off (No Dimming)")
        item_off.connect("activate", self.set_level_0)
        self.menu.append(item_off)
        
        item_light = Gtk.MenuItem(label="🌤️  Light (20%)")
        item_light.connect("activate", self.set_level_1)
        self.menu.append(item_light)
        
        item_medium = Gtk.MenuItem(label="⛅  Medium (40%)")
        item_medium.connect("activate", self.set_level_2)
        self.menu.append(item_medium)
        
        item_dark = Gtk.MenuItem(label="🌥️  Dark (60%)")
        item_dark.connect("activate", self.set_level_3)
        self.menu.append(item_dark)
        
        item_very_dark = Gtk.MenuItem(label="🌙  Very Dark (80%)")
        item_very_dark.connect("activate", self.set_level_4)
        self.menu.append(item_very_dark)
        
        item_ultra = Gtk.MenuItem(label="🌑  Ultra (100%)")
        item_ultra.connect("activate", self.set_level_5)
        self.menu.append(item_ultra)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Warm filter submenu
        warm_menu_item = Gtk.MenuItem(label="🔥 Warm Filter")
        warm_submenu = Gtk.Menu()
        
        warm_off = Gtk.MenuItem(label="❄️  Off (6500K)")
        warm_off.connect("activate", self.set_warm_0)
        warm_submenu.append(warm_off)
        
        warm_1 = Gtk.MenuItem(label="🌡️  Warm 1 (5500K)")
        warm_1.connect("activate", self.set_warm_1)
        warm_submenu.append(warm_1)
        
        warm_2 = Gtk.MenuItem(label="🌡️  Warm 2 (4500K)")
        warm_2.connect("activate", self.set_warm_2)
        warm_submenu.append(warm_2)
        
        warm_3 = Gtk.MenuItem(label="🔥  Warm 3 (3500K)")
        warm_3.connect("activate", self.set_warm_3)
        warm_submenu.append(warm_3)
        
        warm_4 = Gtk.MenuItem(label="🔥  Warm 4 (2700K)")
        warm_4.connect("activate", self.set_warm_4)
        warm_submenu.append(warm_4)
        
        warm_5 = Gtk.MenuItem(label="🕯️  Candle (2000K)")
        warm_5.connect("activate", self.set_warm_5)
        warm_submenu.append(warm_5)
        
        warm_menu_item.set_submenu(warm_submenu)
        self.menu.append(warm_menu_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Profiles submenu
        profiles_menu_item = Gtk.MenuItem(label="📋 Profiles")
        profiles_submenu = Gtk.Menu()
        
        for profile_id, profile_data in PROFILES.items():
            _, _, label, desc = profile_data
            item = Gtk.MenuItem(label=f"{label}")
            item.connect("activate", lambda w, p=profile_id: self.apply_profile(p))
            profiles_submenu.append(item)
        
        profiles_menu_item.set_submenu(profiles_submenu)
        self.menu.append(profiles_menu_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Slider window option
        slider_item = Gtk.MenuItem(label="🎚️  Open Slider...")
        slider_item.connect("activate", self.on_open_slider)
        self.menu.append(slider_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Break reminder toggle
        self.break_menu_item = Gtk.CheckMenuItem(label="⏰ Break Reminder (20 min)")
        self.break_menu_item.set_active(self.break_enabled)
        self.break_menu_item.connect("toggled", self.toggle_break_reminder)
        self.menu.append(self.break_menu_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Current status
        self.status_item = Gtk.MenuItem(label="Status: Off")
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)
        
        # Warm status
        self.warm_status_item = Gtk.MenuItem(label="Warm: Off")
        self.warm_status_item.set_sensitive(False)
        self.menu.append(self.warm_status_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Quit option
        quit_item = Gtk.MenuItem(label="❌  Quit")
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)
        
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
    
    # Individual level setters to avoid closure issues (5 levels)
    def set_level_0(self, widget):
        self.set_dimmer_level(0)
    
    def set_level_1(self, widget):
        self.set_dimmer_level(1)
    
    def set_level_2(self, widget):
        self.set_dimmer_level(2)
    
    def set_level_3(self, widget):
        self.set_dimmer_level(3)
    
    def set_level_4(self, widget):
        self.set_dimmer_level(4)
    
    def set_level_5(self, widget):
        self.set_dimmer_level(5)
    
    # Warm level setters
    def set_warm_0(self, widget):
        self.set_warm_level(0)
    
    def set_warm_1(self, widget):
        self.set_warm_level(1)
    
    def set_warm_2(self, widget):
        self.set_warm_level(2)
    
    def set_warm_3(self, widget):
        self.set_warm_level(3)
    
    def set_warm_4(self, widget):
        self.set_warm_level(4)
    
    def set_warm_5(self, widget):
        self.set_warm_level(5)
    
    def set_dimmer_level(self, level, notify=False):
        """Set the dimmer to specified level (0-5)."""
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
            if notify:
                self.show_notification("🔆 Dimmer", "Off - Full brightness")
        else:
            pct = level * 20
            level_name = LEVEL_NAMES.get(level, f"{pct}%")
            self.status_item.set_label(f"Status: {level_name}")
            
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
            
            # Update icon based on level (5 levels)
            if level <= 2:
                self.indicator.set_icon_full("display-brightness-high-symbolic", f"Dimmer {pct}%")
            elif level <= 3:
                self.indicator.set_icon_full("display-brightness-medium-symbolic", f"Dimmer {pct}%")
            else:
                self.indicator.set_icon_full("display-brightness-low-symbolic", f"Dimmer {pct}%")
            
            if notify:
                self.show_notification("🌙 Dimmer", level_name)
        
        # Save level to config
        self.save_config()
    
    def set_warm_level(self, level, notify=False):
        """Set the warm filter level (0-5) using KDE Night Light."""
        print(f"[DEBUG] Setting warm level to {level}")
        
        self.warm_level = level
        temp = WARM_TEMPS.get(level, 6500)
        
        # Use KDE Night Light via qdbus
        try:
            if level == 0:
                # Stop preview (return to normal/scheduled mode)
                subprocess.run([
                    'qdbus', 'org.kde.KWin', '/org/kde/KWin/NightLight',
                    'org.kde.KWin.NightLight.stopPreview'
                ], stderr=subprocess.DEVNULL, timeout=5)
                print("[DEBUG] Stopped Night Light preview")
            else:
                # Preview the temperature
                subprocess.run([
                    'qdbus', 'org.kde.KWin', '/org/kde/KWin/NightLight',
                    'org.kde.KWin.NightLight.preview', str(temp)
                ], stderr=subprocess.DEVNULL, timeout=5)
                print(f"[DEBUG] Applied Night Light temperature: {temp}K")
        except Exception as e:
            print(f"[ERROR] Failed to set warm filter: {e}")
            return
        
        warm_name = WARM_NAMES.get(level, f"Level {level}")
        
        # Update status item
        if level == 0:
            self.warm_status_item.set_label("Warm: Off")
        else:
            self.warm_status_item.set_label(f"Warm: {warm_name}")
        
        if notify:
            if level == 0:
                self.show_notification("❄️ Warm Filter", "Off - Neutral colors")
            else:
                self.show_notification("🔥 Warm Filter", warm_name)
        
        # Save config
        self.save_config()
    
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
        
        self.set_default_size(450, 380)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self.set_resizable(False)
        
        # Apply dark theme
        self.apply_css()
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(25)
        main_box.set_margin_end(25)
        self.add(main_box)
        
        # ========== DIMMER SECTION ==========
        dimmer_title = Gtk.Label()
        dimmer_title.set_markup("<span size='large' weight='bold'>🌙 Dimmer (Brightness)</span>")
        main_box.pack_start(dimmer_title, False, False, 0)
        
        # Dimmer status label
        self.dimmer_status = Gtk.Label()
        self.update_dimmer_status()
        main_box.pack_start(self.dimmer_status, False, False, 2)
        
        # Dimmer Slider - 5 levels (20% steps)
        self.dimmer_adjustment = Gtk.Adjustment(
            value=self.tray_app.current_level,
            lower=0,
            upper=5,
            step_increment=1,
            page_increment=1,
            page_size=0
        )
        
        self.dimmer_slider = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=self.dimmer_adjustment
        )
        self.dimmer_slider.set_digits(0)
        self.dimmer_slider.set_draw_value(True)
        self.dimmer_slider.set_value_pos(Gtk.PositionType.RIGHT)
        
        # Add marks for dimmer levels
        for i in range(6):
            label = "Off" if i == 0 else f"{i*20}%"
            self.dimmer_slider.add_mark(i, Gtk.PositionType.BOTTOM, label)
        
        self.dimmer_slider.connect("value-changed", self.on_dimmer_changed)
        main_box.pack_start(self.dimmer_slider, False, False, 5)
        
        # Dimmer preset buttons
        dimmer_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dimmer_btn_box.set_halign(Gtk.Align.CENTER)
        
        for label, level in [("Off", 0), ("Light", 1), ("Dark", 3), ("Ultra", 5)]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self.on_dimmer_preset, level)
            dimmer_btn_box.pack_start(btn, False, False, 0)
        
        main_box.pack_start(dimmer_btn_box, False, False, 5)
        
        # Separator
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 10)
        
        # ========== WARM FILTER SECTION ==========
        warm_title = Gtk.Label()
        warm_title.set_markup("<span size='large' weight='bold'>🔥 Warm Filter (Blue Light)</span>")
        main_box.pack_start(warm_title, False, False, 0)
        
        # Warm status label
        self.warm_status = Gtk.Label()
        self.update_warm_status()
        main_box.pack_start(self.warm_status, False, False, 2)
        
        # Warm Slider - 5 levels
        self.warm_adjustment = Gtk.Adjustment(
            value=self.tray_app.warm_level,
            lower=0,
            upper=5,
            step_increment=1,
            page_increment=1,
            page_size=0
        )
        
        self.warm_slider = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=self.warm_adjustment
        )
        self.warm_slider.set_digits(0)
        self.warm_slider.set_draw_value(True)
        self.warm_slider.set_value_pos(Gtk.PositionType.RIGHT)
        
        # Add marks for warm levels
        warm_marks = ["Off", "5500K", "4500K", "3500K", "2700K", "2000K"]
        for i, label in enumerate(warm_marks):
            self.warm_slider.add_mark(i, Gtk.PositionType.BOTTOM, label)
        
        self.warm_slider.connect("value-changed", self.on_warm_changed)
        main_box.pack_start(self.warm_slider, False, False, 5)
        
        # Warm preset buttons
        warm_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        warm_btn_box.set_halign(Gtk.Align.CENTER)
        
        for label, level in [("Off", 0), ("Warm", 2), ("Sunset", 4), ("Candle", 5)]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self.on_warm_preset, level)
            warm_btn_box.pack_start(btn, False, False, 0)
        
        main_box.pack_start(warm_btn_box, False, False, 5)
        
        # ========== ACTION BUTTONS ==========
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        action_box.set_halign(Gtk.Align.END)
        action_box.set_margin_top(10)
        
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
    
    def update_dimmer_status(self):
        """Update the dimmer status label text."""
        level = self.tray_app.current_level
        if level == 0:
            text = "No dimming (Full brightness)"
        else:
            text = LEVEL_NAMES.get(level, f"{level * 20}%")
        self.dimmer_status.set_markup(f"<span size='medium'>{text}</span>")
    
    def update_warm_status(self):
        """Update the warm filter status label text."""
        level = self.tray_app.warm_level
        if level == 0:
            text = "Off - Neutral colors (6500K)"
        else:
            text = WARM_NAMES.get(level, f"Level {level}")
        self.warm_status.set_markup(f"<span size='medium'>{text}</span>")
    
    def on_dimmer_changed(self, widget):
        """Handle dimmer slider value change."""
        level = int(self.dimmer_adjustment.get_value())
        self.tray_app.set_dimmer_level(level)
        self.update_dimmer_status()
    
    def on_dimmer_preset(self, widget, level):
        """Handle dimmer preset button click."""
        self.dimmer_adjustment.set_value(level)
    
    def on_warm_changed(self, widget):
        """Handle warm slider value change."""
        level = int(self.warm_adjustment.get_value())
        self.tray_app.set_warm_level(level)
        self.update_warm_status()
    
    def on_warm_preset(self, widget, level):
        """Handle warm preset button click."""
        self.warm_adjustment.set_value(level)
    
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
        print("  gcc -o dimmer_passthrough dimmer_passthrough.c -lX11 -lXext")
        return 1
    
    # Check if binary is executable
    if not os.access(DIMMER_BINARY, os.X_OK):
        print(f"Error: Dimmer binary is not executable: {DIMMER_BINARY}")
        print("Please run: chmod +x dimmer_passthrough")
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
