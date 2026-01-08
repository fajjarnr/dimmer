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
    """Modern UI Slider window matching CareUEyes design."""
    
    def __init__(self, tray_app):
        super().__init__(title="Dimmer Control")
        self.tray_app = tray_app
        
        self.set_default_size(800, 520)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self.set_resizable(False)
        
        # Apply custom theme
        self.apply_css()
        
        # Main layout container (Horizontal: Sidebar | Content)
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(main_hbox)
        
        # ========== SIDEBAR (Left) ==========
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.sidebar.set_size_request(180, -1)
        self.sidebar.get_style_context().add_class("sidebar")
        main_hbox.pack_start(self.sidebar, False, False, 0)
        
        # Logo area
        logo_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        logo_box.set_margin_top(20)
        logo_box.set_margin_bottom(20)
        logo_box.set_margin_start(15)
        
        logo_icon = Gtk.Image.new_from_icon_name("display-brightness-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        logo_label = Gtk.Label(label="CareUEyes") # Using the requested name
        logo_label.set_markup("<span size='large' weight='bold' color='white'>DimmerEye</span>")
        
        logo_box.pack_start(logo_icon, False, False, 0)
        logo_box.pack_start(logo_label, False, False, 0)
        self.sidebar.pack_start(logo_box, False, False, 0)
        
        # Navigation Buttons
        self.nav_stack = Gtk.Stack()
        self.nav_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        
        bg_group = None
        self.nav_buttons = {}
        
        nav_items = [
            ("Display", "video-display-symbolic", "display_page"),
            ("BreakTimer", "alarm-symbolic", "break_page"),
            ("Focus", "view-fullscreen-symbolic", "placeholder_page"),
            ("Options", "emblem-system-symbolic", "placeholder_page"),
            ("About", "help-about-symbolic", "placeholder_page"),
        ]
        
        for label, icon, page_id in nav_items:
            btn = Gtk.RadioButton.new_with_label_from_widget(bg_group, f"  {label}")
            btn.set_mode(False) # Make it look like a button
            btn.get_style_context().add_class("nav-button")
            
            # Add icon
            image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
            btn.set_image(image)
            btn.set_always_show_image(True)
            
            if bg_group is None:
                bg_group = btn
                btn.set_active(True)
            
            btn.connect("toggled", self.on_nav_toggled, page_id)
            self.sidebar.pack_start(btn, False, False, 0)
            self.nav_buttons[page_id] = btn
            
        # ========== CONTENT (Right) ==========
        content_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_area.get_style_context().add_class("content-area")
        main_hbox.pack_start(content_area, True, True, 0)
        
        # Title Bar / Header (within content area)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_margin_top(10)
        header_box.set_margin_end(10)
        
        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close_btn.get_style_context().add_class("flat-button")
        close_btn.connect("clicked", self.on_hide_window)
        
        header_box.pack_end(close_btn, False, False, 0)
        content_area.pack_start(header_box, False, False, 0)
        
        # Stack for pages
        content_area.pack_start(self.nav_stack, True, True, 0)
        
        # --- PAGE 1: DISPLAY ---
        self.create_display_page()
        
        # --- PAGE 2: BREAK TIMER ---
        self.create_break_page()
        
        # --- PLACEHOLDER PAGE ---
        placeholder = Gtk.Label(label="Feature coming soon...")
        self.nav_stack.add_named(placeholder, "placeholder_page")
        
        # Handle window close
        self.connect("delete-event", self.on_delete)
        
        # Update timer label
        GLib.timeout_add(1000, self.update_timer_ui)
    
    def create_display_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.set_margin_start(40)
        page.set_margin_end(40)
        page.set_margin_top(10)
        page.set_margin_bottom(20)
        
        # 1. Warm Slider
        warm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        wb_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        wb_label.pack_start(Gtk.Label(label="Color Temperature"), False, False, 0)
        self.warm_val_label = Gtk.Label(label="6500K")
        self.warm_val_label.get_style_context().add_class("value-tag")
        wb_label.pack_end(self.warm_val_label, False, False, 0)
        warm_box.pack_start(wb_label, False, False, 0)
        
        self.warm_adj = Gtk.Adjustment(value=self.tray_app.warm_level, lower=0, upper=5, step_increment=1, page_increment=1, page_size=0)
        self.warm_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.warm_adj)
        self.warm_scale.set_draw_value(False)
        self.warm_scale.get_style_context().add_class("thick-slider")
        self.warm_scale.add_mark(0, Gtk.PositionType.BOTTOM, "Less Warm")
        self.warm_scale.add_mark(5, Gtk.PositionType.BOTTOM, "More Warm")
        self.warm_scale.connect("value-changed", self.on_warm_changed)
        warm_box.pack_start(self.warm_scale, False, False, 0)
        
        page.pack_start(warm_box, False, False, 0)
        
        # 2. Brightness Slider
        dim_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        db_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        db_label.pack_start(Gtk.Label(label="Brightness"), False, False, 0)
        self.dim_val_label = Gtk.Label(label="100%")
        self.dim_val_label.get_style_context().add_class("value-tag")
        db_label.pack_end(self.dim_val_label, False, False, 0)
        dim_box.pack_start(db_label, False, False, 0)
        
        self.dim_adj = Gtk.Adjustment(value=self.tray_app.current_level, lower=0, upper=5, step_increment=1, page_increment=1, page_size=0)
        self.dim_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.dim_adj)
        self.dim_scale.set_draw_value(False)
        self.dim_scale.get_style_context().add_class("thick-slider")
        self.dim_scale.add_mark(0, Gtk.PositionType.BOTTOM, "More Bright")
        self.dim_scale.add_mark(5, Gtk.PositionType.BOTTOM, "Less Bright")
        self.dim_scale.connect("value-changed", self.on_dimmer_changed)
        dim_box.pack_start(self.dim_scale, False, False, 0)
        
        page.pack_start(dim_box, False, False, 0)
        
        # 3. Day/Night & Toggle
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        toggle_box.set_halign(Gtk.Align.CENTER)
        
        toggle_label = Gtk.Label(label="Enable day and night feature")
        toggle_label.get_style_context().add_class("grey-text")
        
        self.dn_switch = Gtk.Switch()
        self.dn_switch.set_active(True) # Dummy implementation
        
        toggle_box.pack_start(toggle_label, False, False, 0)
        toggle_box.pack_start(self.dn_switch, False, False, 0)
        
        page.pack_start(toggle_box, False, False, 10)
        
        # 4. Preset Grid (FlowBox)
        flow = Gtk.FlowBox()
        flow.set_valign(Gtk.Align.START)
        flow.set_max_children_per_line(4)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_column_spacing(10)
        flow.set_row_spacing(10)
        
        # Map profiles to buttons
        presets = [
            ("Pause", 0, 0, "off"), # Off
            ("Health", 1, 2, "work"), # Work (Health)
            ("Game", 0, 1, "gaming"),
            ("Movie", 2, 0, "movie"),
            ("Office", 2, 2, "work"), # Similar to Work
            ("Editing", 1, 1, "gaming"), # Bright
            ("Reading", 2, 3, "reading"),
            ("Custom", 0, 0, None) # Placeholder
        ]
        
        for label, d_lvl, w_lvl, prof_id in presets:
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("preset-btn")
            btn.set_size_request(80, 35)
            if prof_id == "work": # Highlight Health/Work as example
                 btn.get_style_context().add_class("preset-active")
            
            btn.connect("clicked", self.on_preset_click, d_lvl, w_lvl)
            flow.add(btn)
            
        page.pack_start(flow, False, False, 0)
        
        # 5. Description
        desc_label = Gtk.Label(label="Slightly lower color temperature and brightness,\ndarker than office mode, suitable for people who are sensitive to light")
        desc_label.set_justify(Gtk.Justification.CENTER)
        desc_label.get_style_context().add_class("grey-text")
        desc_label.set_max_width_chars(50)
        desc_label.set_line_wrap(True)
        
        page.pack_start(desc_label, False, False, 10)
        
        self.nav_stack.add_named(page, "display_page")
        
    def create_break_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.get_style_context().add_class("teal-bg-top") # Special background?
        
        # Top Section (Teal Background with Timer)
        timer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        timer_box.set_size_request(-1, 200)
        timer_box.get_style_context().add_class("timer-container")
        
        lbl_next = Gtk.Label(label="Next break in:")
        lbl_next.get_style_context().add_class("timer-sublabel")
        
        self.timer_display = Gtk.Label(label="00:20:00")
        self.timer_display.get_style_context().add_class("timer-digits")
        
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        controls_box.set_halign(Gtk.Align.CENTER)
        
        btn_coffee = Gtk.Button.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON)
        btn_stop = Gtk.Button(label="STOP")
        btn_stop.get_style_context().add_class("orange-btn")
        btn_stop.set_size_request(120, 40)
        btn_stop.connect("clicked", self.on_stop_timer)
        
        controls_box.pack_start(Gtk.Image.new_from_icon_name("weather-clear-night-symbolic", Gtk.IconSize.DND), False, False, 0) # Coffee icon placeholder
        controls_box.pack_start(btn_stop, False, False, 0)
        controls_box.pack_start(btn_coffee, False, False, 0)
        
        timer_box.pack_start(lbl_next, True, True, 0)
        timer_box.pack_start(self.timer_display, True, True, 0)
        timer_box.pack_start(controls_box, True, True, 20)
        
        page.pack_start(timer_box, False, False, 0)
        
        # Bottom Section (Settings)
        mod_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        mod_box.set_margin_start(40)
        mod_box.set_margin_end(40)
        mod_box.set_margin_top(20)
        
        # Toggle
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row1.pack_start(Gtk.Label(label="Break Reminder Enabled"), False, False, 0)
        self.break_switch = Gtk.Switch()
        self.break_switch.set_active(self.tray_app.break_enabled)
        self.break_switch.connect("state-set", self.on_break_toggled)
        row1.pack_end(self.break_switch, False, False, 0)
        mod_box.pack_start(row1, False, False, 0)
        
        # Interval
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row2.pack_start(Gtk.Label(label="Every"), False, False, 0)
        self.spin_every = Gtk.SpinButton.new_with_range(5, 120, 5)
        self.spin_every.set_value(20)
        row2.pack_end(Gtk.Label(label=" Minutes"), False, False, 0)
        row2.pack_end(self.spin_every, False, False, 10)
        mod_box.pack_start(row2, False, False, 0)
        
        page.pack_start(mod_box, True, True, 0)
        
        self.nav_stack.add_named(page, "break_page")

    def apply_css(self):
        css = b"""
            /* Main Window */
            window { background-color: #ffffff; }
            .sidebar { background-color: #008080; color: white; }
            .content-area { background-color: #ffffff; }
            
            /* Sidebar Buttons */
            .nav-button {
                background-color: transparent;
                color: #e0f2f1;
                border: none;
                border-radius: 0;
                padding: 12px 20px;
                font-weight: bold;
                text-shadow: none;
                box-shadow: none;
            }
            .nav-button:checked {
                background-color: #ffffff;
                color: #008080;
            }
            .nav-button:hover:not(:checked) {
                background-color: #00695c;
            }
            
            /* Sliders */
            .thick-slider trough {
                min-height: 8px;
                border-radius: 4px;
                background-color: #e0e0e0;
            }
            .thick-slider highlight {
                min-height: 8px;
                border-radius: 4px;
                background-color: #009688; /* Teal */
            }
            .thick-slider slider {
                min-width: 24px; min-height: 24px;
                border-radius: 50%;
                background-color: #ffffff;
                border: 2px solid #009688;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            
            /* Presets */
            .preset-btn {
                background-image: none;
                background-color: #e0f2f1;
                color: #00695c;
                border: none;
                border-radius: 4px;
                box-shadow: none;
            }
            .preset-btn:hover { background-color: #b2dfdb; }
            .preset-active { 
                background-color: #009688; 
                color: white; 
            }
            
            /* Timer Page */
            .timer-container {
                background-color: #009688;
                color: white;
            }
            .timer-digits {
                font-size: 64px;
                font-weight: bold;
                color: white;
            }
            .timer-sublabel { font-size: 16px; color: #b2dfdb; }
            
            .orange-btn {
                background-color: #ff9800;
                color: white;
                font-weight: bold;
                border-radius: 20px;
                border: none;
            }
            .orange-btn:hover { background-color: #f57c00; }
            
            .value-tag {
                background-color: #009688;
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            .grey-text { color: #888888; }
            .flat-button { border: none; background: transparent; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_nav_toggled(self, btn, page_name):
        if btn.get_active():
            self.nav_stack.set_visible_child_name(page_name)
    
    def on_hide_window(self, widget):
        self.hide()
        self.tray_app.on_slider_closed()
        return True
        
    def on_delete(self, widget, event):
        self.on_hide_window(widget)
        return True

    def on_dimmer_changed(self, widget):
        val = int(self.dim_adj.get_value())
        if self.tray_app.current_level != val:
            self.tray_app.set_dimmer_level(val)
            pct = 100 - (val * 20)
            self.dim_val_label.set_label(f"{pct}%")
            
    def on_warm_changed(self, widget):
        val = int(self.warm_adj.get_value())
        if self.tray_app.warm_level != val:
            self.tray_app.set_warm_level(val)
            temps = ["6500K", "5500K", "4500K", "3500K", "2700K", "2000K"]
            self.warm_val_label.set_label(temps[val])

    def on_preset_click(self, widget, d_lvl, w_lvl):
        # Update app
        self.tray_app.set_dimmer_level(d_lvl)
        self.tray_app.set_warm_level(w_lvl)
        # Update sliders
        self.dim_adj.set_value(d_lvl)
        self.warm_adj.set_value(w_lvl)
        
    def on_break_toggled(self, switch, state):
        self.tray_app.break_enabled = state
        self.tray_app.toggle_break_reminder(None) # Pass none or handle appropriately in tray_app
        
    def on_stop_timer(self, widget):
        # Just reset to 20 mins for visual, logic is in tray app
        self.tray_app.stop_break_timer()
        self.break_switch.set_active(False)

    def update_timer_ui(self):
        # Simple countdown logic for visual if timer is active
        # In a real app, query tray_app for remaining time
        if self.tray_app.break_enabled:
            # Fake decrement for demo
            self.timer_display.set_markup("<span font_features='tnum'>00:19:59</span>")
        else:
            self.timer_display.set_label("00:20:00")
        return True


def main():
    """Main entry point."""
    global app
    
    # Check if dimmer binary exists
    if not os.path.isfile(DIMMER_BINARY):
        print(f"Error: Dimmer binary not found at {DIMMER_BINARY}")
        print("Please compile it first with:")
        print("  gcc -o bin/dimmer_passthrough c_src/dimmer_passthrough.c -lX11 -lXext")
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
