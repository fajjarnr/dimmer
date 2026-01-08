#!/usr/bin/env python3
import tkinter as tk
import subprocess

root = tk.Tk()
root.title("Dimmer (20% steps)")
root.geometry("300x180")
root.attributes('-topmost', True)

levels = {1:"Light (20%)", 2:"Medium (40%)", 3:"Dark (60%)", 4:"Very Dark (80%)", 5:"Ultra (100%)"}
status = tk.StringVar(value="Dark (60%)")

tk.Label(root, text="Brightness Control", font=('Arial',12,'bold')).pack(pady=10)
tk.Label(root, textvariable=status).pack(pady=5)

def on_change(val):
    l = int(float(val))
    status.set(levels[l])
    subprocess.run(['pkill','-f','dimmer_passthrough'], stderr=subprocess.DEVNULL)
    subprocess.Popen(['./dimmer_passthrough', str(l)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

slider = tk.Scale(root, from_=1, to=5, orient='horizontal', command=on_change)
slider.set(3)
slider.pack(fill='x', padx=20, pady=10)

tk.Button(root, text="Ultra", command=lambda: slider.set(5)).pack(side='left', padx=5, pady=5)
tk.Button(root, text="Dark", command=lambda: slider.set(3)).pack(side='left', padx=5, pady=5)
tk.Button(root, text="Light", command=lambda: slider.set(1)).pack(side='left', padx=5, pady=5)

root.mainloop()
