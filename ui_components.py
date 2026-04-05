# ui_components.py
import threading
from collections import deque
import numpy as np
import sounddevice as sd
import tkinter as tk
from config import SAMPLE_RATE, BLOCK_SIZE

class MicVisualizer:
    """
    Background audio stream that provides data for the visualizer.
    """
    def __init__(self, seconds_buffer=2.0):
        self.samplerate = SAMPLE_RATE
        self.blocksize = BLOCK_SIZE
        self._lock = threading.Lock()
        self._rms = 0.0
        
        maxlen = int(seconds_buffer * SAMPLE_RATE)
        self._wave = deque(maxlen=maxlen)
        self._stream = None
        self._running = False

    def start(self):
        if self._running: return
        self._running = True

        def callback(indata, frames, time_info, status):
            x = indata[:, 0].astype(np.float32)
            # Calculate smoother RMS
            rms = float(np.sqrt(np.mean(x**2)) + 1e-12)
            # Normalize for UI (0.0 to 1.0)
            level = min(1.0, rms * 6.0) 

            with self._lock:
                self._rms = level
                self._wave.extend(x.tolist())

        try:
            self._stream = sd.InputStream(
                channels=1, samplerate=self.samplerate, blocksize=self.blocksize,
                dtype="float32", callback=callback
            )
            self._stream.start()
        except Exception as e:
            print(f"Mic Error: {e}")
            self._running = False

    def stop(self):
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except: pass
            self._stream = None

    def get_data(self, n_samples=800):
        with self._lock:
            level = self._rms
            if not self._wave:
                return level, np.zeros(n_samples)
            wave = np.array(list(self._wave)[-n_samples:], dtype=np.float32)
        return level, wave

class WaveformCanvas(tk.Canvas):
    """
    A custom Tkinter Canvas that draws a cool mirrored waveform.
    """
    def __init__(self, parent, width=600, height=100, bg="#ac7e7e"):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.w = width
        self.h = height
        self.center_y = height // 2

    def update_plot(self, wave_data, is_active=False):
        self.delete("all")
        
        # Draw a center line if inactive
        if not is_active or len(wave_data) < 10:
            self.create_line(0, self.center_y, self.w, self.center_y, fill="#555", width=1)
            return

        # Normalize data
        # Scale amplitude to fit canvas height
        amp_scale = self.h * 0.4 
        step = max(1, len(wave_data) // self.w)
        
        points = []
        for x in range(0, self.w, 2):
            idx = x * step
            if idx >= len(wave_data): break
            
            sample = wave_data[idx]
            # Mirror effect (top and bottom)
            y_offset = int(abs(sample) * amp_scale)
            y1 = self.center_y - y_offset
            y2 = self.center_y + y_offset
            
            # Draw vertical bars for a "digital" look
            # Color based on amplitude
            color = "#00d2d3" if y_offset < 15 else "#ff6b6b"
            self.create_line(x, self.center_y, x, y1, fill=color, width=1)
            self.create_line(x, self.center_y, x, y2, fill=color, width=1)

import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, X, LEFT, RIGHT, Y

class ScrollableHistoryFrame(tb.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, bg="#111827", highlightthickness=0)
        self.scrollbar = tb.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tb.Frame(self.canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)

    def _on_canvas_configure(self, event):
        try:
            self.canvas.itemconfigure(self.window_id, width=event.width)
        except Exception:
            pass

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()


class HistoryCard(tb.Frame):
    def __init__(self, parent, timestamp, src, dst, original, translated, speaker_callback, text_font_size=14, selected_var=None, *args, **kwargs):
        super().__init__(parent, bootstyle="dark", padding=12, *args, **kwargs)

        outer = tb.Frame(self, bootstyle="secondary")
        outer.pack(fill=X, expand=True, padx=6, pady=6)

        top = tb.Frame(outer, bootstyle="secondary")
        top.pack(fill=X, padx=12, pady=(10, 6))

        if selected_var is not None:
            tb.Checkbutton(
                top,
                variable=selected_var,
                bootstyle="success-square-toggle"
            ).pack(side=LEFT, padx=(0, 8))

        tb.Label(
            top,
            text=f"🕒 {timestamp}",
            font=("Segoe UI", 9, "bold"),
            bootstyle="info"
        ).pack(side=LEFT)

        tb.Button(
            top,
            text="🔊",
            width=3,
            bootstyle="success-outline",
            command=lambda: speaker_callback(translated)
        ).pack(side=RIGHT)

        tb.Label(
            outer,
            text=f"{src}  →  {dst}",
            font=("Segoe UI", 10, "bold"),
            bootstyle="warning"
        ).pack(anchor="w", padx=12, pady=(0, 8))

        tb.Label(
            outer,
            text="Original:",
            font=("Segoe UI", 9, "bold"),
            bootstyle="light"
        ).pack(anchor="w", padx=12)

        tb.Label(
            outer,
            text=original,
            wraplength=1500,
            justify="left",
            font=("Segoe UI", max(10, int(text_font_size) - 2)),
            bootstyle="light"
        ).pack(anchor="w", padx=12, pady=(0, 8))

        tb.Label(
            outer,
            text="Translated:",
            font=("Segoe UI", 9, "bold"),
            bootstyle="success"
        ).pack(anchor="w", padx=12)

        tb.Label(
            outer,
            text=translated,
            wraplength=1500,
            justify="left",
            font=("Segoe UI", max(10, int(text_font_size) - 2)),
            bootstyle="light"
        ).pack(anchor="w", padx=12, pady=(0, 12))
