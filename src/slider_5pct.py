#!/usr/bin/env python3
import tkinter as tk
import subprocess

root = tk.Tk()
root.title("Dimmer (5% steps)")
root.geometry("350x180")
root.attributes('-topmost', True)

def get_level_name(l):
    if l <= 4: return "Bright"
    if l <= 10: return "Light"
    if l <= 15: return "Dark"
    return "Very Dark"

status = tk.StringVar(value="50% - Light")

tk.Label(root, text="Brightness Control (Fine)", font=('Arial',12,'bold')).pack(pady=10)
tk.Label(root, textvariable=status).pack(pady=5)

def on_change(val):
    l = int(float(val))
    pct = l * 5
    status.set(f"{pct}% - {get_level_name(l)}")
    subprocess.run(['pkill','-f','dimmer_passthrough_20lvl'], stderr=subprocess.DEVNULL)
    subprocess.Popen(['./dimmer_passthrough_20lvl', str(l)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

slider = tk.Scale(root, from_=1, to=20, orient='horizontal', command=on_change, resolution=1)
slider.set(10)
slider.pack(fill='x', padx=20, pady=10)

tk.Button(root, text="50%", command=lambda: slider.set(10)).pack(side='left', padx=5, pady=5)
tk.Button(root, text="30%", command=lambda: slider.set(6)).pack(side='left', padx=5, pady=5)
tk.Button(root, text="70%", command=lambda: slider.set(14)).pack(side='left', padx=5, pady=5)

def on_close():
    subprocess.run(['pkill','-f','dimmer_passthrough_20lvl'], stderr=subprocess.DEVNULL)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
