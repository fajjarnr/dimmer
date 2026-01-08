# Dimmer - Brightness Control untuk KDE Plasma

Mirip CareUEyes di Windows - overlay gelap dengan kontrol brightness.

## Dependencies

```bash
# Fedora/Nobara
sudo dnf install libX11-devel libXext-devel python3-tkinter

# Ubuntu/Debian
sudo apt install libx11-dev libxext-dev python3-tk
```

## Struktur File

| File | Deskripsi |
|------|-----------|
| `slider_5pct.py` | GUI Slider 5% step (halus) - **RECOMMENDED** |
| `slider_20pct.py` | GUI Slider 20% step (cepat) |
| `dim_control.sh` | Control via command line |
| `dim_hotkeys.sh` | Control untuk KDE shortcuts |
| `dimmer_passthrough` | Binary dimmer (5 level, 20% step) |
| `dimmer_passthrough_20lvl` | Binary dimmer (20 level, 5% step) |

## Cara Pakai

### 1. GUI Slider (Paling Mudah)

```bash
# 5% step (halus, 20 level) - RECOMMENDED untuk presisi!
./slider_5pct.py

# 20% step (cepat, 5 level)
./slider_20pct.py
```

### 2. Command Line

```bash
./dim_control.sh 1    # Light (20%)
./dim_control.sh 3    # Dark (60%)
./dim_control.sh 5    # Ultra (100% - hitam)
./dim_control.sh off  # Matikan dimmer
```

### 3. Keyboard Shortcuts (KDE)

Setup di **System Settings → Shortcuts → Custom Shortcuts**:

| Shortcut | Command |
|----------|---------|
| F3 | `/<path-to-dimmer>/dim_hotkeys.sh ultra` |
| F4 | `/<path-to-dimmer>/dim_hotkeys.sh light` |

> Ganti `<path-to-dimmer>` dengan lokasi folder dimmer Anda.

## Kompilasi (Opsional)

Jika ingin mengkompilasi ulang binary:

```bash
gcc -o dimmer_passthrough dimmer_passthrough.c -lX11 -lXext
gcc -o dimmer_passthrough_20lvl dimmer_passthrough_20lvl.c -lX11 -lXext
```

## Rekomendasi

**Gunakan `slider_5pct.py`** untuk kontrol lebih halus seperti CareUEyes!

20% step lebih cepat tapi kurang presisi. 5% step lebih mirip slider asli CareUEyes.
