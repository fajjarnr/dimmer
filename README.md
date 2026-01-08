# Dimmer - Brightness Control untuk KDE Plasma

Mirip CareUEyes di Windows - overlay gelap dengan kontrol brightness.

## Struktur File
- `dimmer_passthrough` - Binary dimmer (5 level, 20% step)
- `dimmer_passthrough_20lvl` - Binary dimmer (20 level, 5% step)
- `slider_20pct.py` - GUI Slider 20% step (cepat)
- `slider_5pct.py` - GUI Slider 5% step (halus)
- `dimmer_slider.py` - Symlink ke slider_20pct.py
- `dim_control.sh` - Control via command line
- `dim_hotkeys.sh` - Control untuk KDE shortcuts

## Cara Pakai

### 1. GUI Slider (Paling Mudah)
```bash
# 20% step (cepat, 5 level)
./slider_20pct.py

# 5% step (halus, 20 level) - RECOMMENDED untuk presisi!
./slider_5pct.py
```

### 2. Command Line
```bash
./dim_control.sh 1  # Light (20%)
./dim_control.sh 3  # Dark (60%)
./dim_control.sh 5  # Ultra (100% - hitam)
./dim_control.sh off
```

### 3. Keyboard Shortcuts (F3/F4 via KDE)
Setup di System Settings → Shortcuts:
- F3: `/home/jay/Projects/dimmer/dim_hotkeys.sh ultra`
- F4: `/home/jay/Projects/dimmer/dim_hotkeys.sh light`

## Rekomendasi
**Gunakan 5% step (`slider_5pct.py`)** untuk kontrol lebih halus seperti CareUEyes!

20% step lebih cepat tapi kurang presisi. 5% step lebih mirip slider asli CareUEyes.
