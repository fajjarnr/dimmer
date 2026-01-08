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
# Level descriptions for 20-level system (5% steps)
# We won't map every single level to a name, just key ones for the menu
# 0 = Off, 20 = 100% Dark (Ultra)
MENU_LEVELS = {
    0: "Off (0%)",
    4: "Light (20%)",
    8: "Medium (40%)",
    12: "Dark (60%)",
    16: "Very Dark (80%)",
    20: "Ultra (100%)"
}

# Preset profiles: (dimmer_level [0-20], warm_temp [K], label, desc)
# Note: dimmer_level 0 = Off (100% bright), 20 = 100% dim (Black)
# User request: "bright 90%" means 10% dim -> Level 2
# Wait, let's clarify. Usually "brightness 90%" means 10% dimmed.
# If my dimmer levels are "how much to DIM", then:
# 100% Brightness = 0% Dim = Level 0
# 90% Brightness = 10% Dim = Level 2
# 85% Brightness = 15% Dim = Level 3
# 100% Brightness = 0% Dim = Level 0
# 
# Let's map based on "Dimming Level" (Opacity):
# Health: 90% Bright -> 10% Dim -> Level 2
# Game: 90% Bright -> 10% Dim -> Level 2
# Movie: 90% Bright -> 10% Dim -> Level 2
# Office: 85% Bright -> 15% Dim -> Level 3
# Editing: 100% Bright -> 0% Dim -> Level 0
# Reading: 85% Bright -> 15% Dim -> Level 3
#
PROFILES = {
    "health": (2, 5000, "💚 Health", "5000K, 90% Brightness"),
    "game": (2, 6500, "🎮 Game", "6500K, 90% Brightness"),
    "movie": (2, 6000, "🎬 Movie", "6000K, 90% Brightness"),
    "office": (3, 5500, "💼 Office", "5500K, 85% Brightness"),
    "editing": (0, 6500, "🖊️ Editing", "6500K, 100% Brightness"),
    "reading": (3, 5500, "📖 Reading", "5500K, 85% Brightness"),
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
        
        # New format: dim_level, warm_temp, label, desc
        dim_level, warm_temp, label, desc = PROFILES[profile_name]
        self.set_dimmer_level(dim_level, notify=False)
        self.set_warm_level(warm_temp, notify=False)
        self.show_notification(f"{label} Profile", desc)
        
    def build_menu(self):
        """Build the system tray context menu."""
        self.menu = Gtk.Menu()
        
        # Header
        header = Gtk.MenuItem(label="🔆 Dimmer Control")
        header.set_sensitive(False)
        self.menu.append(header)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Quick brightness presets (from MENU_LEVELS)
        # Sort levels to ensure order
        sorted_levels = sorted(MENU_LEVELS.keys())
        
        for level in sorted_levels:
            name = MENU_LEVELS[level]
            # Add emoji if missing (simple heuristic)
            if "Off" in name:
                label = f"☀️  {name}"
            elif "20%" in name:
                label = f"🌤️  {name}"
            elif "40%" in name:
                label = f"⛅  {name}"
            elif "60%" in name:
                label = f"🌥️  {name}"
            elif "80%" in name:
                label = f"🌙  {name}"
            elif "100%" in name:
                label = f"🌑  {name}"
            else:
                label = name
                
            item = Gtk.MenuItem(label=label)
            # Use default arg to capture loop variable
            item.connect("activate", lambda w, l=level: self.set_dimmer_level(l))
            self.menu.append(item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Warm filter submenu
        warm_menu_item = Gtk.MenuItem(label="🔥 Warm Filter")
        warm_submenu = Gtk.Menu()
        
        # Define warm presets for menu
        warm_presets = [
            (6500, "❄️  Off (6500K)"),
            (5500, "🌡️  Warm 1 (5500K)"),
            (4500, "🌡️  Warm 2 (4500K)"),
            (3500, "🔥  Warm 3 (3500K)"),
            (2700, "🔥  Warm 4 (2700K)"),
            (2000, "🕯️  Candle (2000K)")
        ]
        
        for temp, label in warm_presets:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda w, t=temp: self.set_warm_level(t))
            warm_submenu.append(item)
        
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
    
    def set_dimmer_level(self, level, notify=False):
        """Set the dimmer to specified level (0-20)."""
        print(f"[DEBUG] Setting dimmer level to {level}")
        
        # Kill any existing dimmer process
        try:
            subprocess.run(['pkill', '-f', 'dimmer_passthrough'],
                          stderr=subprocess.DEVNULL, timeout=2)
        except subprocess.TimeoutExpired:
            pass
        
        # Clamp level
        level = max(0, min(20, int(level)))
        self.current_level = level
        
        if level == 0:
            self.status_item.set_label("Status: Off")
            self.indicator.set_icon_full("display-brightness-symbolic", "Dimmer Off")
            print("[DEBUG] Dimmer turned off")
            if notify:
                self.show_notification("🔆 Dimmer", "Off - Full brightness")
        else:
            pct = level * 5
            # find closest menu name
            level_name = f"{pct}% Dimmed"
            if level in MENU_LEVELS:
                level_name = MENU_LEVELS[level]
                
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
            
            # Update icon based on level (20 levels)
            if level <= 7:
                self.indicator.set_icon_full("display-brightness-high-symbolic", f"Dimmer {pct}%")
            elif level <= 14:
                self.indicator.set_icon_full("display-brightness-medium-symbolic", f"Dimmer {pct}%")
            else:
                self.indicator.set_icon_full("display-brightness-low-symbolic", f"Dimmer {pct}%")
            
            if notify:
                self.show_notification("🌙 Dimmer", level_name)
        
        # Save level to config
        self.save_config()
    
    def set_warm_level(self, temp, notify=False):
        """Set the warm filter temperature (Kelvin)."""
        print(f"[DEBUG] Setting warm temperature to {temp}K")
        
        self.warm_level = int(temp)
        
        # Use KDE Night Light via qdbus
        try:
            # 6500K is standard daylight/off. 0 also means off.
            if temp == 0 or temp >= 6500:
                # Stop preview (return to normal/scheduled mode)
                subprocess.run([
                    'qdbus', 'org.kde.KWin', '/org/kde/KWin/NightLight',
                    'org.kde.KWin.NightLight.stopPreview'
                ], stderr=subprocess.DEVNULL, timeout=5)
                print("[DEBUG] Stopped Night Light preview")
                status_text = "Off (6500K)"
                notif_text = "Off - Neutral colors"
            else:
                # Preview the temperature
                subprocess.run([
                    'qdbus', 'org.kde.KWin', '/org/kde/KWin/NightLight',
                    'org.kde.KWin.NightLight.preview', str(temp)
                ], stderr=subprocess.DEVNULL, timeout=5)
                print(f"[DEBUG] Applied Night Light temperature: {temp}K")
                status_text = f"{temp}K"
                notif_text = f"Temperature: {temp}K"
                
        except Exception as e:
            print(f"[ERROR] Failed to set warm filter: {e}")
            return
        
        # Update status item
        self.warm_status_item.set_label(f"Warm: {status_text}")
        
        if notify:
            if temp == 0 or temp >= 6500:
                self.show_notification("❄️ Warm Filter", notif_text)
            else:
                self.show_notification("🔥 Warm Filter", notif_text)
        
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
        
        # Track active profile for styling
        self.current_profile_id = None
        self.preset_buttons = {}
        self.updating_from_profile = False  # Flag to prevent slider feedback loop
        
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
        logo_label = Gtk.Label(label="CareUEyes") 
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
        
        # Title Bar / Header
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
        
        # Check initial profile state
        self.check_profile_match()
    
    def create_display_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.set_margin_start(40)
        page.set_margin_end(40)
        page.set_margin_top(10)
        page.set_margin_bottom(20)
        
        # 1. Warm Slider (Kelvin)
        # We model this as 0 (Less Warm/6500K) to 100 (More Warm/2000K) for the slider visual
        warm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        wb_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        wb_label.pack_start(Gtk.Label(label="Color Temperature"), False, False, 0)
        self.warm_val_label = Gtk.Label(label=f"{self.tray_app.warm_level}K")
        self.warm_val_label.get_style_context().add_class("value-tag")
        wb_label.pack_end(self.warm_val_label, False, False, 0)
        warm_box.pack_start(wb_label, False, False, 0)
        
        # Calculate initial slider pos from Kelvin
        # Range: 6500 (0%) -> 2000 (100%)
        # Value = (6500 - Temp) / (6500 - 2000) * 100
        current_k = self.tray_app.warm_level
        if current_k == 0: current_k = 6500
        slider_val = ((6500 - current_k) / 4500) * 100
        slider_val = max(0, min(100, slider_val))
        
        self.warm_adj = Gtk.Adjustment(value=slider_val, lower=0, upper=100, step_increment=1, page_increment=10, page_size=0)
        self.warm_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.warm_adj)
        self.warm_scale.set_draw_value(True)
        self.warm_scale.set_value_pos(Gtk.PositionType.TOP)
        self.warm_scale.get_style_context().add_class("thick-slider")
        self.warm_scale.set_inverted(True)  # Invert: left=warm, right=cool
        self.warm_scale.add_mark(100, Gtk.PositionType.BOTTOM, "More Warm")
        self.warm_scale.add_mark(0, Gtk.PositionType.BOTTOM, "Less Warm")
        self.warm_scale.connect("value-changed", self.on_warm_changed)
        self.warm_scale.connect("format-value", self.format_warm_value)
        warm_box.pack_start(self.warm_scale, False, False, 0)
        
        page.pack_start(warm_box, False, False, 0)
        
        # 2. Brightness Slider
        # 0 (Less Bright/Dark) -> 100 (More Bright)
        # App Level 0 = Bright, 20 = Dark.
        # Slider 0 = Level 20. Slider 100 = Level 0.
        # Slider = 100 - (Level * 5)
        dim_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        db_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        db_label.pack_start(Gtk.Label(label="Brightness"), False, False, 0)
        
        curr_pct = 100 - (self.tray_app.current_level * 5)
        self.dim_val_label = Gtk.Label(label=f"{curr_pct}%")
        self.dim_val_label.get_style_context().add_class("value-tag")
        db_label.pack_end(self.dim_val_label, False, False, 0)
        dim_box.pack_start(db_label, False, False, 0)
        
        self.dim_adj = Gtk.Adjustment(value=curr_pct, lower=0, upper=100, step_increment=5, page_increment=10, page_size=0)
        self.dim_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.dim_adj)
        self.dim_scale.set_draw_value(True)
        self.dim_scale.set_value_pos(Gtk.PositionType.TOP)
        self.dim_scale.get_style_context().add_class("thick-slider")
        self.dim_scale.add_mark(0, Gtk.PositionType.BOTTOM, "Less Bright")
        self.dim_scale.add_mark(100, Gtk.PositionType.BOTTOM, "More Bright")
        self.dim_scale.connect("value-changed", self.on_dimmer_changed)
        self.dim_scale.connect("format-value", self.format_dim_value)
        dim_box.pack_start(self.dim_scale, False, False, 0)
        
        page.pack_start(dim_box, False, False, 0)
        
        # 3. Toggle Feature (Dummy)
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        toggle_box.set_halign(Gtk.Align.CENTER)
        toggle_label = Gtk.Label(label="Enable day and night feature")
        toggle_label.get_style_context().add_class("grey-text")
        self.dn_switch = Gtk.Switch()
        self.dn_switch.set_active(True)
        toggle_box.pack_start(toggle_label, False, False, 0)
        toggle_box.pack_start(self.dn_switch, False, False, 0)
        page.pack_start(toggle_box, False, False, 10)
        
        # 4. Preset Grid
        flow = Gtk.FlowBox()
        flow.set_valign(Gtk.Align.START)
        flow.set_max_children_per_line(4)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_column_spacing(10)
        flow.set_row_spacing(10)
        
        # Requested Profiles
        # Format: (Label, ProfileID)
        presets_list = [
            ("Pause", "pause"),   # Special: Off/Off
            ("Health", "health"),
            ("Game", "game"),
            ("Movie", "movie"),
            ("Office", "office"),
            ("Editing", "editing"),
            ("Reading", "reading"),
            ("Custom", "custom")
        ]
        
        # "Pause" -> Dim 0 (100%), Warm 6500 (Off)
        # "Custom" -> Placeholder
        
        for label, pid in presets_list:
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("preset-btn")
            btn.set_size_request(80, 35)
            btn.connect("clicked", self.on_preset_click, pid)
            flow.add(btn)
            self.preset_buttons[pid] = btn
            
        page.pack_start(flow, False, False, 0)
        
        # Description
        desc_label = Gtk.Label(label="Slightly lower color temperature and brightness,\ndarker than office mode, suitable for people who are sensitive to light")
        desc_label.set_justify(Gtk.Justification.CENTER)
        desc_label.get_style_context().add_class("grey-text")
        desc_label.set_max_width_chars(50)
        desc_label.set_line_wrap(True)
        page.pack_start(desc_label, False, False, 10)
        
        self.nav_stack.add_named(page, "display_page")
        
    def create_break_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.get_style_context().add_class("teal-bg-top")
        
        # Timer Display
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
        
        controls_box.pack_start(Gtk.Image.new_from_icon_name("weather-clear-night-symbolic", Gtk.IconSize.DND), False, False, 0)
        controls_box.pack_start(btn_stop, False, False, 0)
        controls_box.pack_start(btn_coffee, False, False, 0)
        
        timer_box.pack_start(lbl_next, True, True, 0)
        timer_box.pack_start(self.timer_display, True, True, 0)
        timer_box.pack_start(controls_box, True, True, 20)
        
        page.pack_start(timer_box, False, False, 0)
        
        # Settings
        mod_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        mod_box.set_margin_start(40)
        mod_box.set_margin_end(40)
        mod_box.set_margin_top(20)
        
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row1.pack_start(Gtk.Label(label="Break Reminder Enabled"), False, False, 0)
        self.break_switch = Gtk.Switch()
        self.break_switch.set_active(self.tray_app.break_enabled)
        self.break_switch.connect("state-set", self.on_break_toggled)
        row1.pack_end(self.break_switch, False, False, 0)
        mod_box.pack_start(row1, False, False, 0)
        
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
                color: #009688;
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
        if self.updating_from_profile:
            return
            
        # Slider is 0-100% Brightness
        # App expects Level 0 (100% bright) to 20 (0% bright)
        slider_val = int(self.dim_adj.get_value())
        
        # Percentage of brightness: 100% -> Level 0. 0% -> Level 20.
        dim_pct = 100 - slider_val
        level = int(dim_pct / 5)
        
        # Only apply if changed
        if self.tray_app.current_level != level:
            self.tray_app.set_dimmer_level(level)
            self.dim_val_label.set_label(f"{slider_val}%")
            self.check_profile_match()
            
    def on_warm_changed(self, widget):
        if self.updating_from_profile:
            return
            
        # Slider is 0-100% Warmth
        # 0% = 6500K, 100% = 2000K
        slider_val = self.warm_adj.get_value()
        
        # Temp = 6500 - (slider * 45) -> 4500 range / 100 = 45
        temp = 6500 - (slider_val * 45)
        # Snap to 100s
        temp = int(round(temp / 100) * 100)
        
        if self.tray_app.warm_level != temp:
            self.tray_app.set_warm_level(temp)
            self.warm_val_label.set_label(f"{temp}K")
            self.check_profile_match()
    
    def format_dim_value(self, scale, value):
        """Format brightness slider value for display."""
        return f"{int(value)}%"
    
    def format_warm_value(self, scale, value):
        """Format warm slider value for display as Kelvin."""
        temp = 6500 - (value * 45)
        return f"{int(temp)}K"

    def on_preset_click(self, widget, pid):
        # Set active button styling
        self.update_active_button(pid)
        
        if pid == "custom":
            return
            
        if pid == "pause":
            d_lvl = 0
            w_temp = 6500
        else:
            if pid in PROFILES:
                d_lvl, w_temp, _, _ = PROFILES[pid]
            else:
                return

        # Apply to app
        self.tray_app.set_dimmer_level(d_lvl)
        self.tray_app.set_warm_level(w_temp)
        
        # Block slider signals during update to prevent feedback loop
        self.updating_from_profile = True
        
        # Update sliders
        self.dim_adj.set_value(100 - (d_lvl * 5))
        self.dim_val_label.set_label(f"{100 - (d_lvl * 5)}%")
        
        # Update warm slider. Temp -> 0-100
        # Val = (6500 - Temp) / 45
        slider_val = (6500 - w_temp) / 45
        self.warm_adj.set_value(slider_val)
        self.warm_val_label.set_label(f"{w_temp}K")
        
        # Re-enable slider signals
        self.updating_from_profile = False
        
    def update_active_button(self, active_pid):
        for pid, btn in self.preset_buttons.items():
            ctx = btn.get_style_context()
            if pid == active_pid:
                ctx.add_class("preset-active")
            else:
                ctx.remove_class("preset-active")
                
    def check_profile_match(self):
        # Check if current setting matches a profile
        curr_d = self.tray_app.current_level
        curr_w = self.tray_app.warm_level
        if curr_w == 0: curr_w = 6500
        
        found = False
        
        # Check pause
        if curr_d == 0 and curr_w >= 6500:
             self.update_active_button("pause")
             return
             
        for pid, data in PROFILES.items():
            d, w, _, _ = data
            if curr_d == d and abs(curr_w - w) < 200: # Tolerance for temp
                self.update_active_button(pid)
                found = True
                break
        
        if not found:
            self.update_active_button("custom")
        
    def on_break_toggled(self, switch, state):
        self.tray_app.break_enabled = state
        self.tray_app.toggle_break_reminder(None)
        
    def on_stop_timer(self, widget):
        self.tray_app.stop_break_timer()
        self.break_switch.set_active(False)

    def update_timer_ui(self):
        if self.tray_app.break_enabled:
            # Simplistic countdown visualization
            import time
            remaining = "20:00" # Placeholder
            self.timer_display.set_markup(f"<span font_features='tnum'>{remaining}</span>")
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
