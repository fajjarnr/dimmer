# Dimmer - Brightness & Warm Filter Control untuk KDE Plasma

Mirip CareUEyes di Windows - overlay gelap dengan kontrol brightness + warm filter (blue light reduction).

## Dependencies

```bash
# Fedora/Nobara
sudo dnf install libX11-devel libXext-devel python3-gobject gtk3 libappindicator-gtk3

# Ubuntu/Debian
sudo apt install libx11-dev libxext-dev python3-gi gir1.2-appindicator3-0.1
```

## Struktur File

| File                  | Deskripsi                                  |
|-----------------------|--------------------------------------------|
| `dimmer_tray.py`      | **🌟 System Tray App** - RECOMMENDED       |
| `slider_20pct.py`     | GUI Slider 20% step (standalone)           |
| `slider_5pct.py`      | GUI Slider 5% step (halus)                 |
| `dim_control.sh`      | Control via command line                   |
| `dim_hotkeys.sh`      | Control untuk KDE shortcuts                |
| `dimmer_passthrough`  | Binary dimmer (5 level, 20% step)          |

## Cara Pakai

### 🌟 System Tray (RECOMMENDED)

Aplikasi berjalan di **system tray** dengan fitur lengkap:

```bash
./dimmer_tray.py
```

**Fitur Utama:**

- 🔔 Icon di system tray
- 🖱️ Klik kanan untuk menu preset:
  - **Dimmer**: Off, 20%, 40%, 60%, 80%, 100%
  - **Warm Filter**: Off, 5500K, 4500K, 3500K, 2700K, 2000K (via KDE Night Light)
- 🎚️ Slider popup untuk kontrol visual (Dimmer + Warm)
- 💾 **Auto-save** settings (restore saat startup)
- 🌙 Icon berubah sesuai level brightness
- 🚀 Support autostart saat login

### 🔥 Warm Filter (Blue Light Reduction)

Menggunakan **KDE Night Light** secara native untuk mengurangi blue light:

| Level   | Temperature | Penggunaan           |
|---------|-------------|----------------------|
| Off     | 6500K       | Normal siang hari    |
| Warm 1  | 5500K       | Sedikit hangat       |
| Warm 2  | 4500K       | Sore hari            |
| Warm 3  | 3500K       | Malam hari           |
| Warm 4  | 2700K       | Sangat hangat        |
| Candle  | 2000K       | Seperti lilin        |

### Setup Autostart

```bash
# Copy ke autostart folder
cp dimmer-tray.desktop ~/.config/autostart/
```

---

## GUI Slider (Standalone)

```bash
# 20% step (cepat, 5 level)
./slider_20pct.py

# 5% step (halus, 20 level)
./slider_5pct.py
```

## Command Line

```bash
./dim_control.sh 1    # Light (20%)
./dim_control.sh 3    # Dark (60%)
./dim_control.sh 5    # Ultra (100% - hitam)
./dim_control.sh off  # Matikan dimmer
```

## Config File

Settings disimpan di:

```text
~/.config/dimmer/config.json
```

Format:

```json
{
  "level": 3,
  "warm": 2
}
```

## Kompilasi (Opsional)

Jika ingin mengkompilasi ulang binary:

```bash
gcc -o dimmer_passthrough dimmer_passthrough.c -lX11 -lXext
gcc -o dimmer_passthrough_20lvl dimmer_passthrough_20lvl.c -lX11 -lXext
```

## Catatan

- **Wayland**: Dimmer overlay bekerja via XWayland, warm filter menggunakan KDE Night Light native
- **Keyboard Shortcuts**: Tidak tersedia secara langsung (Keybinder tidak support Wayland). Gunakan KDE System Settings → Shortcuts untuk setup custom shortcuts jika diperlukan.
