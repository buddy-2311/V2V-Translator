import threading
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog

import ttkbootstrap as tb
from ttkbootstrap.constants import LEFT, BOTTOM, X, BOTH, HORIZONTAL, WORD, END, RIGHT
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets.scrolled import ScrolledText

import config
import utils
from engine import Engine
from ui_components import ScrollableHistoryFrame, HistoryCard
import custom_db

engine = Engine()


class ModernVoiceApp(tb.Window):
    def __init__(self):
        super().__init__(themename=config.THEME_NAME)

        self.configure(bg="#111827")
        self.title("Translator — Your voice in any language")

        # Branding icon removed intentionally

        try:
            self.state("zoomed")
        except Exception:
            self.geometry("1200x850")
        self.minsize(1000, 750)

        # --- State ---
        self.processing_file = None
        self.processing_files = []
        self.is_processing_files = False
        self.is_recording = False

        # Wake gating
        self.is_armed = False
        self.first_intro_done = False
        self.app_state = "PASSIVE"  # PASSIVE | PROCESSING

        # --- Variables ---
        self.var_in_lang = tb.StringVar(value="English")
        self.var_out_lang = tb.StringVar(value="Hindi")
        self.var_duration = tb.IntVar(value=5)
        self.var_status = tb.StringVar(value="Say your wake name to activate")
        self.var_theme = tb.StringVar(value=config.THEME_NAME)
        self.var_tts_speed = tb.IntVar(value=100)
        self.var_location_state = tb.StringVar()
        self.var_punctuation = tb.StringVar(value="")
        self.var_autoplay_audio = tb.BooleanVar(value=True)
        self.var_typing_animation = tb.BooleanVar(value=True)
        self.var_noisy_room = tb.BooleanVar(value=getattr(config, "NOISY_ROOM_MODE", True))
        self.var_wake_word = tb.StringVar(value="Nova")
        self.var_custom_wake_word = tb.StringVar(value="")
        self.var_end_keywords = tb.StringVar(value="ok, done")
        self.var_history_search = tb.StringVar(value="")
        self.var_font_size = tb.IntVar(value=18)

        self._history_all_rows = []
        self._history_filtered_rows = []
        self._history_selection_vars = {}

        self.location_to_lang = {
            # Indian states
            "gujarat": "gu",
            "maharashtra": "mr",
            "punjab": "pa",
            "west bengal": "bn",
            "tamil nadu": "ta",
            "karnataka": "kn",
            "kerala": "ml",
            "rajasthan": "hi",
            "uttar pradesh": "hi",
            "bihar": "hi",
            "odisha": "or",
            "assam": "as",
            "telangana": "te",
            "andhra pradesh": "te",
            "jammu and kashmir": "ks",
            # Countries
            "india": "hi",
            "pakistan": "ur",
            "bangladesh": "bn",
            "nepal": "hi",
            "sri lanka": "ta",
            "uae": "ar",
            "united arab emirates": "ar",
            "saudi arabia": "ar",
            "qatar": "ar",
            "oman": "ar",
            "kuwait": "ar",
            "egypt": "ar",
            "france": "fr",
            "germany": "de",
            "spain": "es",
            "italy": "it",
            "russia": "ru",
            "japan": "ja",
            "china": "zh-CN",
            "south korea": "ko",
            "korea": "ko",
            "united kingdom": "en",
            "uk": "en",
            "england": "en",
            "canada": "en",
            "usa": "en",
            "united states": "en",
            "america": "en",
            "australia": "en",
            "mexico": "es"
        }

        # Layout
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()
        self.var_out_lang.trace_add("write", self._toggle_location_state_ui)

        # Start disabled until wake+intro
        self._set_record_button_enabled(False)

        if not engine.mic_available:
            self.var_status.set("Mic unavailable (PyAudio missing). Use Upload File mode.")
        else:
            threading.Thread(target=self._wake_listener_loop, daemon=True).start()

        self.protocol("WM_DELETE_WINDOW", self._shutdown)

    # ---------------- UI ----------------
    def _build_sidebar(self):
        sidebar = tb.Frame(self, bootstyle="secondary", width=240)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)

        title_frame = tb.Frame(sidebar, bootstyle="secondary")
        title_frame.pack(pady=(40, 50), fill=X)

        tb.Label(title_frame, text="🌐", font=("Arial", 34),
                 bootstyle="inverse-secondary", justify="center").pack()
        tb.Label(title_frame, text="Translator", font=("Arial", 16, "bold"),
                 bootstyle="warning", justify="center").pack()
        tb.Label(title_frame, text="Your voice in any language", font=("Arial", 10, "bold"),
                 bootstyle="light", justify="center").pack()

        self._add_nav_btn(sidebar, "🎙  TRANSLATOR", lambda: self.notebook.select(0))
        self._add_nav_btn(sidebar, "📜  HISTORY", lambda: self.notebook.select(1))
        self._add_nav_btn(sidebar, "⚙  SETTINGS", lambda: self.notebook.select(2))

        info_frame = tb.Frame(sidebar, bootstyle="secondary")
        info_frame.pack(side=BOTTOM, fill=X, pady=20)
        tb.Label(info_frame, text="v3.2.0 Pro", font=("Consolas", 9),
                 bootstyle="inverse-secondary", justify="center").pack()

    def _add_nav_btn(self, parent, text, command):
        btn_frame = tb.Frame(parent, bootstyle="secondary")
        btn_frame.pack(fill=X, pady=1)
        tb.Button(
            btn_frame,
            text=text,
            command=command,
            bootstyle="secondary",
            cursor="hand2",
            width=20
        ).pack(fill=X, ipady=10, padx=10)

    def _build_main_area(self):
        self.notebook = tb.Notebook(self, bootstyle="dark")
        self.notebook.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # Translator tab
        self.tab_trans = tb.Frame(self.notebook)
        self.notebook.add(self.tab_trans, text="Translator")
        self._build_translator_ui(self.tab_trans)

        # History tab (NOW BUILDS UI + LOADS HISTORY)
        self.tab_hist = tb.Frame(self.notebook, padding=30)
        self.notebook.add(self.tab_hist, text="History")
        self._build_history_ui(self.tab_hist)

        # Settings tab
        self.tab_set = tb.Frame(self.notebook, padding=30)
        self.notebook.add(self.tab_set, text="Settings")
        self._build_settings_ui(self.tab_set)

        # Auto refresh history whenever user clicks History tab
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_translator_ui(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        header = tb.Frame(parent, bootstyle="dark", padding=(20, 15))
        header.grid(row=0, column=0, sticky="ew")

        lang_frame = tb.Frame(header, bootstyle="dark")
        lang_frame.pack(anchor="center")

        self._create_lang_combo(lang_frame, "FROM", self.var_in_lang)
        tb.Label(lang_frame, text="  ➜  ", font=("Arial", 20), bootstyle="light").pack(side=LEFT)
        self._create_lang_combo(lang_frame, "TO", self.var_out_lang)

        self.location_frame = tb.Frame(header, bootstyle="dark")
        tb.Label(
            self.location_frame,
            text="Enter State / Country",
            font=("Arial", 8, "bold"),
            bootstyle="secondary"
        ).pack(side=LEFT, padx=(0, 8))
        tb.Entry(
            self.location_frame,
            textvariable=self.var_location_state,
            width=24
        ).pack(side=LEFT)
        tb.Label(
            self.location_frame,
            text="Example: Gujarat, Punjab, India, Canada, France, Japan",
            font=("Arial", 8),
            bootstyle="secondary"
        ).pack(side=LEFT, padx=(8, 0))
        self._toggle_location_state_ui()

        tb.Label(
            header,
            text="Tip: choose 'Location-Based Language' from the TO dropdown to translate by state or country.",
            font=("Arial", 8),
            bootstyle="secondary"
        ).pack(anchor="center", pady=(6, 0))

        workspace = tb.Frame(parent, padding=20)
        workspace.grid(row=1, column=0, sticky="nsew")

        paned = ttk.PanedWindow(workspace, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        # --- SOURCE BOX (Using GRID to lock buttons in place) ---
        f_in = tb.Labelframe(paned, text=" Source Audio/Text ", bootstyle="info", padding=10)
        f_in.columnconfigure(0, weight=1)
        f_in.rowconfigure(0, weight=1) # Forces text box to stretch, locks row 1 at the bottom

        self.txt_in = ScrolledText(f_in, font=("Segoe UI", 18), bootstyle="info", wrap=WORD)
        self.txt_in.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        in_btn_frame = tb.Frame(f_in)
        in_btn_frame.grid(row=1, column=0, sticky="ew")
        
        tb.Button(
            in_btn_frame, 
            text="▶ Play Source", 
            bootstyle="info", 
            command=self._play_input_audio
        ).pack(side=LEFT)
        
        paned.add(f_in, weight=1)

        # --- RESULT BOX (Using GRID to lock buttons in place) ---
        f_out = tb.Labelframe(paned, text=" Translated Result ", bootstyle="success", padding=10)
        f_out.columnconfigure(0, weight=1)
        f_out.rowconfigure(0, weight=1)

        self.txt_out = ScrolledText(f_out, font=("Segoe UI", 18), bootstyle="success", wrap=WORD)
        self.txt_out.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        self.lbl_punctuation = tb.Label(
            f_out,
            textvariable=self.var_punctuation,
            font=("Segoe UI", 10, "italic"),
            bootstyle="warning"
        )
        # Hidden by default per latest UI request.
        self.lbl_punctuation.grid_forget()

        out_btn_frame = tb.Frame(f_out)
        out_btn_frame.grid(row=1, column=0, sticky="ew")
        
        tb.Button(
            out_btn_frame, 
            text="▶ Play Result", 
            bootstyle="success", 
            command=self._play_output_audio
        ).pack(side=LEFT)
        
        tb.Button(
            out_btn_frame, 
            text="📋 Copy", 
            bootstyle="outline-success", 
            command=self._copy_text
        ).pack(side=RIGHT)
        
        paned.add(f_out, weight=1)

        # --- BOTTOM DECK (Unchanged) ---
        deck = tb.Frame(parent, bootstyle="secondary", padding=20)
        deck.grid(row=2, column=0, sticky="ew")
        deck.columnconfigure(1, weight=1)

        # LEFT
        d_left = tb.Frame(deck, bootstyle="secondary")
        d_left.grid(row=0, column=0, sticky="w")

        tb.Button(d_left, text="📁 Upload File", bootstyle="outline-light",
                  command=self._upload_file, width=15).pack(side=LEFT, padx=(0, 20))

        tb.Label(d_left, text="DURATION:", font=("Arial", 8, "bold"),
                 bootstyle="inverse-secondary").pack(side=LEFT, padx=(0, 5))

        self.lbl_dur = tb.Label(d_left, text=f"{self.var_duration.get()}s",
                                font=("Consolas", 12, "bold"), bootstyle="warning")
        self.lbl_dur.pack(side=LEFT, padx=5)

        self.duration_scale = tb.Scale(
            d_left, from_=5, to=60, variable=self.var_duration, length=160, bootstyle="warning",
            command=lambda v: self.lbl_dur.config(text=f"{int(float(v))}s")
        )
        self.duration_scale.pack(side=LEFT)

        # CENTER
        d_center = tb.Frame(deck, bootstyle="secondary")
        d_center.grid(row=0, column=1)

        self.lbl_status = tb.Label(d_center, textvariable=self.var_status, font=("Segoe UI", 10),
                                   bootstyle="inverse-secondary")
        self.lbl_status.pack(pady=(0, 5))

        # Waveform box removed by user request.

        btn_row = tb.Frame(d_center, bootstyle="secondary")
        btn_row.pack()

        self.btn_record = tb.Button(
            btn_row,
            text="🎤 START RECORDING",
            bootstyle="danger",
            command=self._start_record,
            width=20
        )
        self.btn_record.pack(side=LEFT, ipady=10, padx=(0, 10))

        self.btn_stop = tb.Button(
            btn_row,
            text="STOP ⏹",
            bootstyle="danger-outline",
            command=self._stop_all_actions,
            width=12
        )
        self.btn_stop.pack(side=LEFT, ipady=10, padx=(0, 10))

        self.btn_clear = tb.Button(
            btn_row,
            text="🗑 CLEAR",
            bootstyle="warning-outline",
            command=self._clear_screen,
            width=12
        )
        self.btn_clear.pack(side=LEFT, ipady=10, padx=(0, 10))

        self.btn_repeat = tb.Button(
            btn_row,
            text="🔁 REPEAT",
            bootstyle="info-outline",
            command=self._repeat_last_output,
            width=12
        )
        # Hidden by request.

        # RIGHT
        d_right = tb.Frame(deck, bootstyle="secondary")
        d_right.grid(row=0, column=2, sticky="e")

        tb.Label(d_right, text="SPEED:", font=("Arial", 8, "bold"),
                 bootstyle="inverse-secondary").pack(side=LEFT, padx=(0, 5))
        tb.Label(d_right, text="Slow", font=("Arial", 8),
                 bootstyle="inverse-secondary").pack(side=LEFT)
        tb.Scale(d_right, from_=0, to=100, variable=self.var_tts_speed,
                 length=100, bootstyle="info").pack(side=LEFT, padx=5)
        tb.Label(d_right, text="Normal", font=("Arial", 8),
                 bootstyle="inverse-secondary").pack(side=LEFT, padx=(0, 15))
    # ---------------- HISTORY TAB ----------------
    def _build_history_ui(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        top = tb.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(1, weight=1)

        tb.Label(
            top,
            text="Translation History",
            font=("Segoe UI", 16, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        tool_row = tb.Frame(top)
        tool_row.grid(row=1, column=0, columnspan=3, sticky="ew")
        tool_row.columnconfigure(1, weight=1)

        tb.Label(tool_row, text="Search:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.ent_history_search = tb.Entry(tool_row, textvariable=self.var_history_search, width=36)
        self.ent_history_search.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.ent_history_search.bind("<Return>", lambda e: self._search_history())

        tb.Button(tool_row, text="Search", bootstyle="success-outline", command=self._search_history, width=10).grid(row=0, column=2, padx=(0, 8))
        tb.Button(tool_row, text="Export CSV", bootstyle="outline-info", command=self._export_history_csv, width=12).grid(row=0, column=3, padx=(0, 8))
        tb.Button(tool_row, text="Export TXT", bootstyle="outline-warning", command=self._export_history_txt, width=12).grid(row=0, column=4, padx=(0, 8))
        tb.Button(tool_row, text="Delete Selected", bootstyle="danger-outline", command=self._delete_selected_history, width=16).grid(row=0, column=5, padx=(0, 8))
        tb.Button(top, text="🔄 Refresh", bootstyle="outline-info", command=self._load_history).grid(row=0, column=2, sticky="e")

        self.history_view = ScrollableHistoryFrame(parent)
        self.history_view.grid(row=1, column=0, sticky="nsew")

        self._load_history()

    def _collect_all_history_rows(self):
        rows = []
        try:
            rows.extend(custom_db.get_history_items(None))
        except Exception:
            pass
        try:
            rows.extend(utils.read_all_history())
        except Exception:
            pass

        normalized = []
        seen = set()
        for r in rows:
            try:
                ts, src, dst, orig, trans = r
            except ValueError:
                continue
            item = (
                str(ts or ""),
                str(src or ""),
                str(dst or ""),
                str(orig or ""),
                str(trans or "")
            )
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)

        normalized.sort(key=lambda x: x[0], reverse=True)
        return normalized

    def _render_history_rows(self, rows):
        self.history_view.clear()
        self._history_selection_vars = {}

        if not rows:
            tb.Label(
                self.history_view.inner,
                text="No history found.",
                font=("Segoe UI", 11),
                bootstyle="secondary"
            ).pack(anchor="center", pady=20)
            return

        for ts, src, dst, orig, trans in rows:
            row_key = (str(ts or ""), str(src or ""), str(dst or ""), str(orig or ""), str(trans or ""))
            selected_var = tb.BooleanVar(value=False)
            self._history_selection_vars[row_key] = selected_var
            card = HistoryCard(
                self.history_view.inner,
                timestamp=ts,
                src=src,
                dst=dst,
                original=orig,
                translated=trans,
                speaker_callback=self._play_history_audio,
                text_font_size=int(float(self.var_font_size.get())),
                selected_var=selected_var
            )
            card.pack(fill=X, expand=True, pady=6)

    def _load_history(self):
        self._history_all_rows = self._collect_all_history_rows()
        self._history_filtered_rows = list(self._history_all_rows)
        self._render_history_rows(self._history_filtered_rows)

    def _search_history(self):
        query = (self.var_history_search.get() or "").strip().lower()
        if not query:
            self._history_filtered_rows = list(self._history_all_rows)
        else:
            self._history_filtered_rows = [
                row for row in self._history_all_rows
                if query in " ".join(str(v).lower() for v in row)
            ]
        self._render_history_rows(self._history_filtered_rows)
        self.var_status.set(f"History matches: {len(self._history_filtered_rows)}")

    def _clear_history_search(self):
        self.var_history_search.set("")
        self._history_filtered_rows = list(self._history_all_rows)
        self._render_history_rows(self._history_filtered_rows)

    def _export_history_csv(self):
        rows = self._history_filtered_rows or self._history_all_rows
        path = filedialog.asksaveasfilename(
            title="Export History as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "From", "To", "Original", "Translated"])
            writer.writerows(rows)
        self.var_status.set("History exported as CSV.")

    def _export_history_txt(self):
        rows = self._history_filtered_rows or self._history_all_rows
        path = filedialog.asksaveasfilename(
            title="Export History as TXT",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            for ts, src, dst, orig, trans in rows:
                f.write(f"[{ts}] {src} -> {dst}\n")
                f.write(f"Original: {orig}\n")
                f.write(f"Translated: {trans}\n")
                f.write("-" * 60 + "\n")
        self.var_status.set("History exported as TXT.")

    def _delete_selected_history(self):
        selected_rows = [
            row_key for row_key, var in self._history_selection_vars.items()
            if bool(var.get())
        ]
        if not selected_rows:
            self.var_status.set("No history selected.")
            return

        deleted_db = 0
        deleted_csv = 0
        try:
            deleted_db = custom_db.delete_history_items(selected_rows)
        except Exception:
            pass
        try:
            deleted_csv = utils.delete_history_items(selected_rows)
        except Exception:
            pass

        total_deleted = max(len(selected_rows), deleted_db + deleted_csv)
        self.var_history_search.set("")
        self._load_history()
        self.var_status.set(f"Deleted {total_deleted} history item(s).")

    def _on_tab_changed(self, event):
        try:
            idx = self.notebook.index(self.notebook.select())
            if idx == 1:
                self._load_history()
        except Exception:
            pass

    # ---------------- Settings ----------------
    def _build_settings_ui(self, parent):
        parent.columnconfigure(0, weight=1)

        f_visual = tb.Labelframe(parent, text=" Visual Preferences ", padding=20, bootstyle="primary")
        f_visual.pack(fill=X, anchor="n", pady=(0, 14))
        f_visual.columnconfigure(1, weight=1)

        tb.Label(f_visual, text="Interface Theme:", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=(0, 15), pady=6)
        themes = ["superhero", "cyborg", "darkly", "solar", "flatly", "journal", "litera", "cosmo", "minty", "pulse", "morph", "vapor"]
        cb_theme = tb.Combobox(f_visual, values=themes, state="readonly", textvariable=self.var_theme, width=20)
        cb_theme.grid(row=0, column=1, sticky="w", pady=6)
        cb_theme.bind("<<ComboboxSelected>>", self._change_theme)

        tb.Label(f_visual, text="Font Size:", font=("Segoe UI", 12)).grid(row=1, column=0, sticky="w", padx=(0, 15), pady=6)
        tb.Scale(f_visual, from_=12, to=28, variable=self.var_font_size, length=220, bootstyle="info", command=lambda v: self._apply_font_size()).grid(row=1, column=1, sticky="w", pady=6)

        f_voice = tb.Labelframe(parent, text=" Voice & Wake Word ", padding=20, bootstyle="info")
        f_voice.pack(fill=X, anchor="n", pady=(0, 14))
        for i in range(3):
            f_voice.columnconfigure(i, weight=1 if i == 2 else 0)

        tb.Label(f_voice, text="Wake name:", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=(0, 15), pady=6)
        wake_options = ["Nova", "Veeva", "Khushi", "Zoya", "Aira", "Custom"]
        cb_wake = tb.Combobox(f_voice, values=wake_options, state="readonly", textvariable=self.var_wake_word, width=18)
        cb_wake.grid(row=0, column=1, sticky="w", pady=6)
        cb_wake.bind("<<ComboboxSelected>>", lambda e: self._toggle_custom_wake_ui())

        self.custom_wake_entry = tb.Entry(f_voice, textvariable=self.var_custom_wake_word, width=28)
        self.custom_wake_hint = tb.Label(f_voice, text="Type your own wake name, like Miko or Arya", bootstyle="secondary")
        self._toggle_custom_wake_ui()

        tb.Checkbutton(
            f_voice,
            text="Auto play translated voice",
            variable=self.var_autoplay_audio,
            bootstyle="success-round-toggle"
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=6)

        tb.Checkbutton(
            f_voice,
            text="Typing animation for output",
            variable=self.var_typing_animation,
            bootstyle="info-round-toggle"
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=6)

        tb.Checkbutton(
            f_voice,
            text="Noisy room mode",
            variable=self.var_noisy_room,
            bootstyle="warning-round-toggle",
            command=self._apply_runtime_settings
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=6)

        f_location = tb.Labelframe(parent, text=" Location-Based Translation ", padding=20, bootstyle="warning")
        f_location.pack(fill=X, anchor="n", pady=(0, 14))
        tb.Label(
            f_location,
            text="Use a state or country name when 'Location-Based Language' is selected.\nExamples: Gujarat, Maharashtra, India, Canada, France, Japan, UAE",
            justify="left",
            bootstyle="light"
        ).pack(anchor="w")

        tb.Label(parent, text="Designed for Windows 10/11", bootstyle="secondary").pack(side=BOTTOM, pady=10)

    def _apply_font_size(self):
        try:
            size = int(float(self.var_font_size.get()))
        except Exception:
            size = 18
        try:
            self.txt_in.text.configure(font=("Segoe UI", size))
            self.txt_out.text.configure(font=("Segoe UI", size))
        except Exception:
            pass
        try:
            self._render_history_rows(self._history_filtered_rows or self._history_all_rows)
        except Exception:
            pass

    def _toggle_custom_wake_ui(self):
        if not hasattr(self, "custom_wake_entry"):
            return
        if (self.var_wake_word.get() or "").strip().lower() == "custom":
            self.custom_wake_entry.grid(row=0, column=2, sticky="w", padx=(12, 0), pady=6)
            self.custom_wake_hint.grid(row=1, column=2, sticky="w", padx=(12, 0), pady=2)
        else:
            self.custom_wake_entry.grid_remove()
            self.custom_wake_hint.grid_remove()

    def _apply_runtime_settings(self):
        try:
            config.NOISY_ROOM_MODE = bool(self.var_noisy_room.get())
        except Exception:
            pass

    def _get_active_wake_word(self):
        selected_raw = (self.var_wake_word.get() or "Nova").strip()
        selected = selected_raw.lower()
        if selected == "custom":
            custom = (self.var_custom_wake_word.get() or "").strip().lower()
            return custom or "nova"
        return selected

    def _handle_runtime_command(self, text):
        spoken = " ".join((text or "").strip().lower().replace(",", " ").replace(".", " ").split())
        if not spoken:
            return None

        wake = self._get_active_wake_word()
        command_map = {
            f"{wake} stop": "stop",
            f"{wake} clear the screen": "clear",
            f"{wake} repeat": "repeat",
            f"{wake} start listening": "start_listening",
        }
        for phrase, cmd in command_map.items():
            if phrase in spoken:
                return cmd

        return engine.handle_nova_command(spoken)

    def _get_output_lang_values(self):
        values = [v for v in config.LANGUAGES.keys() if v != "Auto-Detect"]
        if "Location-Based Language" in values:
            values.remove("Location-Based Language")
        values.insert(0, "Location-Based Language")
        return values

    def _refresh_out_lang_values(self, combo=None):
        try:
            target_combo = combo or getattr(self, "out_lang_combo", None)
            if target_combo is not None:
                target_combo.configure(values=self._get_output_lang_values())
        except Exception:
            pass

    def _create_lang_combo(self, parent, label_text, variable):
        f = tb.Frame(parent, bootstyle="dark")
        f.pack(side=LEFT, padx=10)
        tb.Label(f, text=label_text, font=("Arial", 8, "bold"),
                 bootstyle="secondary").pack(anchor="w")

        values = list(config.LANGUAGES.keys())
        combo_width = 18
        postcommand = None

        if label_text == "TO":
            values = self._get_output_lang_values()
            combo_width = 28
            postcommand = lambda: self._refresh_out_lang_values()

        cb = tb.Combobox(
            f,
            textvariable=variable,
            values=values,
            state="readonly",
            width=combo_width,
            font=("Segoe UI", 11),
            postcommand=postcommand
        )
        cb.pack()

        if label_text == "TO":
            self.out_lang_combo = cb
            self._refresh_out_lang_values(cb)

    def _toggle_location_state_ui(self, *args):
        if not hasattr(self, "location_frame"):
            return

        if self.var_out_lang.get() == "Location-Based Language":
            self.location_frame.pack(anchor="center", pady=(8, 0))
        else:
            self.location_frame.pack_forget()

    def _normalize_location_key(self, value):
        value = (value or "").strip().lower()
        value = value.replace(".", " ").replace(",", " ")
        return " ".join(value.split())

    def _resolve_output_language(self):
        out_name = self.var_out_lang.get()

        if out_name != "Location-Based Language":
            cfg = config.LANGUAGES[out_name]
            return out_name, cfg["tr"], cfg.get("tts", "en")

        state_key = self._normalize_location_key(self.var_location_state.get())
        mapped_lang = self.location_to_lang.get(state_key, "hi")

        if mapped_lang == "ks" and "Kashmiri" in config.LANGUAGES:
            cfg = config.LANGUAGES["Kashmiri"]
            return "Kashmiri", cfg["tr"], cfg.get("tts", "en")

        for lang_name, cfg in config.LANGUAGES.items():
            if cfg.get("tr") == mapped_lang:
                return lang_name, cfg["tr"], cfg.get("tts", "en")

        cfg = config.LANGUAGES["Hindi"]
        return "Hindi", cfg["tr"], cfg.get("tts", "en")

    # ---------------- Helpers ----------------
    def _set_record_button_enabled(self, enabled: bool):
        if enabled:
            self.btn_record.configure(state="normal", bootstyle="danger")
        else:
            self.btn_record.configure(state="disabled", bootstyle="secondary")

    def _show_listening_popup(self):
        def _open():
            try:
                if hasattr(self, "_listen_popup") and self._listen_popup and self._listen_popup.winfo_exists():
                    self._listen_popup.deiconify()
                    self._start_listening_popup_animation()
                    return
            except Exception:
                pass

            self._listen_popup = tb.Toplevel(self)
            self._listen_popup.overrideredirect(True)
            self._listen_popup.attributes("-topmost", True)

            transparent_key = "#ff00ff"
            try:
                self._listen_popup.configure(bg=transparent_key)
                self._listen_popup.wm_attributes("-transparentcolor", transparent_key)
            except Exception:
                self._listen_popup.configure(bg=transparent_key)

            size = 220
            try:
                root_x = self.winfo_rootx()
                root_y = self.winfo_rooty()
                root_w = self.winfo_width()
                root_h = self.winfo_height()
                x = root_x + max(0, (root_w - size) // 2)
                y = root_y + max(0, (root_h - size) // 2)
            except Exception:
                x, y = 300, 220
            self._listen_popup.geometry(f"{size}x{size}+{x}+{y}")

            self._listen_canvas = tk.Canvas(
                self._listen_popup,
                width=size,
                height=size,
                bg=transparent_key,
                highlightthickness=0,
                bd=0,
            )
            self._listen_canvas.pack(fill=BOTH, expand=True)

            base = os.path.dirname(os.path.abspath(__file__))
            self._listen_mic_img = None
            try:
                self._listen_mic_img = tk.PhotoImage(file=os.path.join(base, "mic_overlay.png"))
            except Exception:
                self._listen_mic_img = None

            self._listen_pulse_step = 0
            self._listen_pulse_job = None
            self._listen_popup_size = size
            self._draw_listening_popup_frame()
            self._start_listening_popup_animation()

            self._listen_popup.bind("<Button-1>", lambda e: self._stop_all_actions())
            self._listen_canvas.bind("<Button-1>", lambda e: self._stop_all_actions())
        self.after(0, _open)

    def _draw_listening_popup_frame(self):
        try:
            c = self._listen_canvas
            size = int(getattr(self, "_listen_popup_size", 220))
            c.delete("all")

            pulse = getattr(self, "_listen_pulse_step", 0) % 12
            outer_sizes = [172, 180, 188, 196, 204, 210, 204, 196, 188, 180, 172, 166]
            inner_sizes = [130, 136, 142, 148, 154, 160, 154, 148, 142, 136, 130, 124]
            outer = outer_sizes[pulse]
            inner = inner_sizes[pulse]
            for ring_size, color, stip in [(outer, "#9edfeb", "gray50"), (inner, "#48c2da", "gray25")]:
                pad = (size - ring_size) // 2
                c.create_oval(pad, pad, size - pad, size - pad, fill=color, outline="", stipple=stip)

            if self._listen_mic_img is not None:
                c.create_image(size // 2, size // 2, image=self._listen_mic_img)
            else:
                cx = size // 2
                c.create_oval(cx - 20, 56, cx + 20, 126, fill="#ffffff", outline="#ffffff")
                c.create_rectangle(cx - 20, 92, cx + 20, 126, fill="#ffffff", outline="#ffffff")
                c.create_arc(cx - 42, 76, cx + 42, 152, start=180, extent=180, style=tk.ARC, outline="#ffffff", width=8)
                c.create_line(cx, 152, cx, 170, width=8, fill="#ffffff", capstyle=tk.ROUND)
                c.create_line(cx - 24, 176, cx + 24, 176, width=8, fill="#ffffff", capstyle=tk.ROUND)
        except Exception:
            pass

    def _start_listening_popup_animation(self):
        def _animate():
            try:
                if not (hasattr(self, "_listen_popup") and self._listen_popup and self._listen_popup.winfo_exists()):
                    return
                self._listen_pulse_step = (getattr(self, "_listen_pulse_step", 0) + 1) % 12
                self._draw_listening_popup_frame()
                self._listen_pulse_job = self.after(180, _animate)
            except Exception:
                self._listen_pulse_job = None
        try:
            if getattr(self, "_listen_pulse_job", None):
                self.after_cancel(self._listen_pulse_job)
        except Exception:
            pass
        _animate()

    def _update_listening_popup(self, text):
        # Intentionally icon-only popup, so no live transcript text is shown.
        return

    def _hide_listening_popup(self):
        def _close():
            try:
                if getattr(self, "_listen_pulse_job", None):
                    self.after_cancel(self._listen_pulse_job)
                    self._listen_pulse_job = None
            except Exception:
                pass
            try:
                if hasattr(self, "_listen_popup") and self._listen_popup and self._listen_popup.winfo_exists():
                    self._listen_popup.destroy()
            except Exception:
                pass
        self.after(0, _close)

    def _get_end_phrase_candidates(self):
        wake = self._get_active_wake_word().strip().lower()
        kws = [k.strip().lower() for k in (self.var_end_keywords.get() or "ok, done").replace(";", ",").split(",") if k.strip()]
        phrases = []
        for kw in kws or ["ok", "done"]:
            phrases.extend([f"{kw} {wake}", f"{wake} {kw}"])
        return phrases

    def _strip_stop_phrase(self, text):
        original = (text or "").strip()
        lowered = " ".join(original.lower().replace(",", " ").replace(".", " ").split())
        for phrase in self._get_end_phrase_candidates():
            if lowered.endswith(phrase):
                # Remove from original conservatively by word count
                words = original.split()
                pcount = len(phrase.split())
                if len(words) >= pcount:
                    return " ".join(words[:-pcount]).strip(), True
        return original, False

    def _record_until_stop_phrase(self, in_cfg, is_auto):
        accumulated = []
        detected_name = self.var_in_lang.get()
        in_tr = in_cfg.get("tr", "auto")
        last_loudness = 0.0
        silent_rounds = 0

        # Long-form chunked listening until stop phrase is spoken or Stop is pressed.
        while not engine.stop_requested:
            current_preview = " ".join(accumulated).strip()
            self._update_listening_popup(current_preview or "Listening")
            audio = engine.record_audio(duration=5)
            try:
                last_loudness = engine.calculate_loudness(audio)
            except Exception:
                last_loudness = 0.0

            if is_auto:
                chunk_text, detected_name, detected_tr = self._auto_detect_transcribe(audio)
                if detected_tr:
                    in_tr = detected_tr
            else:
                chunk_text, _ = engine.speech_to_text(audio, lang=in_cfg["sr"])
                detected_name = self.var_in_lang.get()
                in_tr = in_cfg["tr"]

            chunk_text = (chunk_text or "").strip()
            if not chunk_text:
                silent_rounds += 1
                # allow ongoing conversation silence without stopping automatically
                if silent_rounds >= 24:  # about 2 minutes of silence safeguard
                    break
                continue

            silent_rounds = 0
            cleaned, should_end = self._strip_stop_phrase(chunk_text)
            if cleaned:
                accumulated.append(cleaned)
                self._update_listening_popup(" ".join(accumulated))
            if should_end:
                break

        return " ".join(accumulated).strip(), detected_name, in_tr, last_loudness

    def _change_theme(self, event=None):
        self.style.theme_use(self.var_theme.get())

    def _copy_text(self):
        txt = self.txt_out.text.get("1.0", END).strip()
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.var_status.set("Copied to clipboard!")

    def _update_input_text(self, text):
        self.txt_in.text.delete("1.0", END)
        self.txt_in.text.insert("1.0", text or "")

    def _update_output_text(self, text):
        # Clear the text box
        self.txt_out.text.delete("1.0", END)
        text = text or ""
        
        # Create a unique ID for this typing job to prevent overlapping animations
        if hasattr(self, "_typing_id"):
            self._typing_id += 1
        else:
            self._typing_id = 1
            
        current_job = self._typing_id
        typing_speed = 30  # Milliseconds between each letter (adjust for speed)

        def type_char(index=0):
            # If a new translation started, kill this older animation loop
            if self._typing_id != current_job:
                return
            if engine.stop_requested:
                return

            if index < len(text):
                # Insert one character
                self.txt_out.text.insert(END, text[index])
                # Auto-scroll to the bottom so the "cursor" is always visible
                self.txt_out.text.see(END)
                # Schedule the next character
                self.after(typing_speed, type_char, index + 1)
            else:
                # Optional: Update status when typing finishes
                pass

        # Start the animation
        if not self.var_typing_animation.get():
            self.txt_out.text.insert("1.0", text)
            return
        type_char()
    # ---------------- Wake word ----------------
    def _wake_listener_loop(self):
        while True:
            if self.app_state != "PASSIVE":
                time.sleep(0.12)
                continue

            detected = engine.wait_for_wake_word_blocking(self._get_active_wake_word(), lang=config.LANGUAGES["English"]["sr"])
            if not detected:
                continue

            self.app_state = "PROCESSING"
            self.after(0, self._handle_wake)

    def _handle_wake(self):
        if not self.first_intro_done:
            self.first_intro_done = True
            wake_name = self._get_active_wake_word().title()
            self.var_status.set(f"Activating {wake_name}...")

            engine.speak(f"Hello. I am {wake_name}. Your intelligent voice translator. I am ready. Let's start translation.", lang="en")

            self.is_armed = True
            self._set_record_button_enabled(True)
            self.var_status.set(f"{wake_name} is ready. Click Start Recording.")
            self.app_state = "PASSIVE"
            return

        wake_name = self._get_active_wake_word().title()
        self.var_status.set(f"{wake_name}: Ready.")
        engine.speak(f"I'm here. {wake_name} is listening.", lang="en")
        self.is_armed = True
        self._set_record_button_enabled(True)
        self.app_state = "PASSIVE"

    # ---------------- File upload ----------------
    def _upload_file(self):
        file_paths = filedialog.askopenfilenames(
            title="Select File(s)",
            filetypes=[
                ("All supported files", "*.wav *.mp3 *.m4a *.ogg *.opus *.aac *.flac *.wma *.mp4 *.mov *.avi *.mkv *.webm *.mpeg *.mpg *.txt *.md *.csv *.json *.py *.js *.html *.css *.xml *.yaml *.yml *.log *.pdf *.docx *.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff"),
                ("Audio / Video", "*.wav *.mp3 *.m4a *.ogg *.opus *.aac *.flac *.wma *.mp4 *.mov *.avi *.mkv *.webm *.mpeg *.mpg"),
                ("Documents", "*.txt *.md *.csv *.json *.pdf *.docx"),
                ("Images", "*.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not file_paths:
            return

        self.processing_files.extend(list(file_paths))

        if not self.is_processing_files:
            self.is_processing_files = True
            threading.Thread(target=self._process_file_thread, daemon=True).start()
        else:
            self.var_status.set(f"Added {len(file_paths)} file(s) to queue.")

    def _process_file_thread(self):
        try:
            while self.processing_files:
                path = self.processing_files.pop(0)
                self.processing_file = path
                self.after(0, lambda p=path: self.var_status.set(f"Processing file: {os.path.basename(p)}"))

                in_name = self.var_in_lang.get()
                in_cfg = config.LANGUAGES[in_name]
                is_auto = in_cfg.get("is_auto", False)
                in_sr = "en-IN" if is_auto else in_cfg["sr"]
                in_tr = "auto" if is_auto else in_cfg["tr"]
                resolved_out_name, out_tr, out_tts = self._resolve_output_language()

                self.after(0, lambda: self._update_input_text(""))
                self.after(0, lambda: self._update_output_text(""))

                if engine._is_audio_or_video(path):
                    self.after(0, lambda p=path: self.var_status.set(f"Transcribing: {os.path.basename(p)}"))
                    text, _ = engine.transcribe_file(path, lang=in_sr)
                else:
                    self.after(0, lambda p=path: self.var_status.set(f"Reading: {os.path.basename(p)}"))
                    text = engine.extract_text_from_file(path)

                text = (text or "").strip()
                translated = ""
                read_failed = (
                    not text
                    or text.startswith("Unsupported file type")
                    or text.startswith("Could not extract text")
                    or text.startswith("Could not read text")
                    or text.startswith("Image read failed")
                    or text.startswith("DOCX support requires")
                    or text.startswith("Image OCR support requires")
                )
                if not read_failed:
                    self.after(0, lambda p=path: self.var_status.set(f"Translating: {os.path.basename(p)}"))
                    translated = engine.translate_text(text, src=in_tr, dest=out_tr)

                self.after(0, lambda t=text: self._update_input_text(t))
                self.after(0, lambda t=translated: self._update_output_text(t))
                self.after(0, lambda: self.var_punctuation.set(""))

                if translated and not translated.startswith("Translation failed") and self.var_autoplay_audio.get():
                    threading.Thread(target=engine.speak, args=(translated,), kwargs={"lang": out_tts}, daemon=True).start()

                status_msg = f"Done: {os.path.basename(path)}" if (text and not read_failed) else (text or f"Could not read anything from {os.path.basename(path)}.")
                self.after(0, lambda m=status_msg: self.var_status.set(m))

                if text and translated and not translated.startswith("Translation failed"):
                    utils.log_history(in_name, resolved_out_name, text, translated)
                    custom_db.save_history_item(in_name, resolved_out_name, text, translated)

        except Exception as e:
            self.after(0, lambda err=str(e): Messagebox.show_error(err, "File Error"))
            self.after(0, lambda: self.var_status.set("File error occurred."))
        finally:
            self.processing_file = None
            self.is_processing_files = False

    # ---------------- Recording (single only) ----------------
    def _start_record(self):
        if not self.is_armed:
            return

        if not engine.mic_available:
            Messagebox.show_error("Mic not available (PyAudio missing). Use Upload File mode.", "Mic Error")
            return

        if self.is_recording:
            return

        self.is_recording = True
        self.btn_record.configure(text="PROCESSING...", bootstyle="warning", state="disabled")
        threading.Thread(target=self._single_record_thread, daemon=True).start()

    # ── langdetect code → (Google STT sr code, display name) ──────────────────
    _LANG_MAP = {
        "en":    ("en-IN",  "English"),
        "hi":    ("hi-IN",  "Hindi"),
        "gu":    ("gu-IN",  "Gujarati"),
        "pa":    ("pa-IN",  "Punjabi"),
        "mr":    ("mr-IN",  "Marathi"),
        "ta":    ("ta-IN",  "Tamil"),
        "te":    ("te-IN",  "Telugu"),
        "bn":    ("bn-IN",  "Bengali"),
        "es":    ("es-ES",  "Spanish"),
        "fr":    ("fr-FR",  "French"),
        "de":    ("de-DE",  "German"),
        "ja":    ("ja-JP",  "Japanese"),
        "zh-cn": ("zh-CN",  "Chinese"),
        "ko":    ("ko-KR",  "Korean"),
        "ru":    ("ru-RU",  "Russian"),
        "it":    ("it-IT",  "Italian"),
    }

    def _char_script_ratios(self, text: str):
        counts = {
            "latin": 0,
            "devanagari": 0,
            "gujarati": 0,
            "gurmukhi": 0,
            "bengali": 0,
            "tamil": 0,
            "telugu": 0,
        }
        letters = 0
        for ch in text:
            o = ord(ch)
            if ch.isalpha() or (0x0900 <= o <= 0x0C7F):
                letters += 1
            if ('A' <= ch <= 'Z') or ('a' <= ch <= 'z'):
                counts["latin"] += 1
            elif 0x0900 <= o <= 0x097F:
                counts["devanagari"] += 1
            elif 0x0A80 <= o <= 0x0AFF:
                counts["gujarati"] += 1
            elif 0x0A00 <= o <= 0x0A7F:
                counts["gurmukhi"] += 1
            elif 0x0980 <= o <= 0x09FF:
                counts["bengali"] += 1
            elif 0x0B80 <= o <= 0x0BFF:
                counts["tamil"] += 1
            elif 0x0C00 <= o <= 0x0C7F:
                counts["telugu"] += 1
        if letters == 0:
            return {k: 0.0 for k in counts}
        return {k: v / letters for k, v in counts.items()}

    def _score_candidate(self, text: str, lang_code: str) -> float:
        text = (text or "").strip()
        if not text:
            return -1e9

        lower = text.lower()
        ratios = self._char_script_ratios(text)
        score = min(len(text), 60) * 0.15

        expected_scripts = {
            "en": "latin",
            "hi": "devanagari",
            "mr": "devanagari",
            "gu": "gujarati",
            "pa": "gurmukhi",
            "bn": "bengali",
            "ta": "tamil",
            "te": "telugu",
        }
        wrong_scripts = {
            "en": ["devanagari", "gujarati", "gurmukhi", "bengali", "tamil", "telugu"],
            "hi": ["latin", "gujarati", "gurmukhi", "bengali", "tamil", "telugu"],
            "mr": ["latin", "gujarati", "gurmukhi", "bengali", "tamil", "telugu"],
            "gu": ["latin", "devanagari", "gurmukhi", "bengali", "tamil", "telugu"],
            "pa": ["latin", "devanagari", "gujarati", "bengali", "tamil", "telugu"],
            "bn": ["latin", "devanagari", "gujarati", "gurmukhi", "tamil", "telugu"],
            "ta": ["latin", "devanagari", "gujarati", "gurmukhi", "bengali", "telugu"],
            "te": ["latin", "devanagari", "gujarati", "gurmukhi", "bengali", "tamil"],
        }
        expected = expected_scripts.get(lang_code)
        if expected:
            score += ratios.get(expected, 0.0) * 12.0
            score -= sum(ratios.get(s, 0.0) for s in wrong_scripts.get(lang_code, [])) * 7.0

        markers = {
            "en": [" i ", " want ", " need ", " to ", " now", " please", " am ", " are ", " sleep", " home"],
            "hi": ["मैं", "मुझे", "है", "हूं", "क्या", "क्यों", "आप", "नहीं", "कहाँ", "कैसे", "और"],
            "mr": ["मी", "मला", "आहे", "नाही", "तू", "तुम्ही", "काय", "कुठे", "घरी", "जायचे", "आता"],
            "gu": ["હું", "મને", "છે", "શું", "તમે", "નથી", "ક્યાં", "કેવી", "ઘરે", "જવું", "હવે"],
            "pa": ["ਮੈਂ", "ਮੈਨੂੰ", "ਹੈ", "ਨਹੀਂ", "ਕੀ", "ਕਿੱਥੇ", "ਤੁਸੀਂ", "ਘਰ", "ਜਾਣਾ"],
            "bn": ["আমি", "আমার", "আছে", "নয়", "কোথায়", "তুমি"],
            "ta": ["நான்", "எனக்கு", "இல்லை", "எங்கே", "வேண்டும்"],
            "te": ["నేను", "నాకు", "లేదు", "ఎక్కడ", "కావాలి"],
        }
        for m in markers.get(lang_code, []):
            if lang_code == "en":
                if m in f" {lower} ":
                    score += 2.0
            else:
                if m in text:
                    score += 2.5

        # Strong penalty for transliterated English accidentally recognized in Indic scripts.
        translit_bad = ["आई ", "वांट", "टू", "स्लीप", "नाउ", "ओके", "प्लीज"]
        if lang_code in {"hi", "mr"} and any(b in text for b in translit_bad):
            score -= 6.0
        if lang_code == "gu" and any(b in text for b in ["આઈ", "વૉન્ટ", "ટુ", "નાઉ"]):
            score -= 6.0

        return score

    def _auto_detect_transcribe(self, audio):
        """
        Deterministic multi-pass auto-detect focused on the user's main languages.
        Returns: (final_text, detected_display_name, detected_tr_code)
        """
        candidates = [
            ("English", "en", "en-IN"),
            ("Hindi", "hi", "hi-IN"),
            ("Gujarati", "gu", "gu-IN"),
            ("Marathi", "mr", "mr-IN"),
            ("Punjabi", "pa", "pa-IN"),
            ("Bengali", "bn", "bn-IN"),
            ("Tamil", "ta", "ta-IN"),
            ("Telugu", "te", "te-IN"),
        ]

        results = []
        for display_name, tr_code, sr_code in candidates:
            txt, conf = engine.speech_to_text(audio, lang=sr_code)
            txt = (txt or "").strip()
            if not txt:
                continue
            score = self._score_candidate(txt, tr_code)
            # Slight preference to the user's most common languages.
            if tr_code in {"en", "hi", "gu", "mr", "pa"}:
                score += 0.75
            results.append((score, display_name, tr_code, txt, conf))

        if not results:
            return "", "Unknown", "auto"

        results.sort(key=lambda x: x[0], reverse=True)
        best_score, best_name, best_code, best_text, _ = results[0]

        # Prefer English transcript when the top non-English result is just transliterated English.
        english = next((r for r in results if r[2] == "en"), None)
        if english:
            en_score, _, _, en_text, _ = english
            ratios = self._char_script_ratios(best_text)
            if ratios.get("latin", 0.0) < 0.25 and en_score >= best_score - 1.5:
                if any(w in f" {en_text.lower()} " for w in [" i ", " want ", " need ", " sleep", " home", " now "]):
                    best_name, best_code, best_text = "English", "en", en_text

        return best_text, best_name, best_code

    def _single_record_thread(self):
        self.app_state = "PROCESSING"
        try:
            engine.reset_stop_flag()
            sec = int(self.var_duration.get())
            in_name = self.var_in_lang.get()
            out_name = self.var_out_lang.get()

            in_cfg  = config.LANGUAGES[in_name]
            is_auto = in_cfg.get("is_auto", False)
            resolved_out_name, out_tr, out_tts = self._resolve_output_language()

            self.after(0, lambda: self.var_status.set(
                "Listening... Speak in ANY language." if is_auto else "Listening... Speak now."
            ))
            self._show_listening_popup()

            audio = engine.record_audio(duration=sec)
            if is_auto:
                self.after(0, lambda: self.var_status.set("Detecting language..."))
                raw_text, detected_name, detected_tr = self._auto_detect_transcribe(audio)
                in_tr = detected_tr
                self.after(0, lambda dn=detected_name: self.var_status.set(f"Detected: {dn} — Translating..."))
                conf = 0.9
            else:
                self.after(0, lambda: self.var_status.set("Recognizing..."))
                raw_text, conf = engine.speech_to_text(audio, lang=in_cfg["sr"])
                in_tr = in_cfg["tr"]
                detected_name = in_name

            if not raw_text.strip():
                self.after(0, lambda: self.var_status.set("No speech detected. Check Windows default input mic."))
                return

            command = self._handle_runtime_command(raw_text)
            if command == "stop":
                self.after(0, self._stop_all_actions)
                return
            elif command == "clear":
                self.after(0, self._clear_screen)
                return
            elif command == "repeat":
                self.after(0, self._repeat_last_output)
                return
            elif command == "start_listening":
                self.after(0, lambda: self.var_status.set(f"{self._get_active_wake_word()} is listening..."))
                return

            loudness = engine.calculate_loudness(audio)
            final_text = engine.apply_smart_punctuation(raw_text, loudness)
            punctuation_info = utils.analyze_punctuation(final_text)

            self.after(0, lambda: self._update_input_text(final_text))
            self.after(0, lambda: self.var_punctuation.set(punctuation_info))

            trans = engine.translate_text(final_text, src=in_tr, dest=out_tr)

            self.after(0, lambda: self._update_output_text(trans))
            self.after(0, lambda dn=detected_name: self.var_status.set(
                f"Done. (Detected: {dn})" if is_auto else f"Done. (conf={conf:.2f})"
            ))

            if trans and not trans.startswith("Translation failed"):
                if self.var_autoplay_audio.get():
                    engine.speak(trans, lang=out_tts)
                log_src = f"Auto({detected_name})" if is_auto else in_name
                utils.log_history(log_src, resolved_out_name, final_text, trans)
                custom_db.save_history_item(log_src, resolved_out_name, final_text, trans)

        except Exception as e:
            self.after(0, lambda: Messagebox.show_error(str(e), "Mic Error"))
            self.after(0, lambda: self.var_status.set("Mic error occurred."))
        finally:
            self._hide_listening_popup()
            self.app_state = "PASSIVE"
            self.is_recording = False
            self.after(0, lambda: self.btn_record.configure(
                text="🎤 START RECORDING",
                bootstyle="danger",
                state="normal"
            ))

    def _stop_all_actions(self):
        engine.stop_all()

        if hasattr(self, "_typing_id"):
            self._typing_id += 1

        self.is_recording = False
        self.var_status.set("Stopped.")
        self.btn_record.configure(
            text="🎤 START RECORDING",
            bootstyle="danger",
            state="normal"
        )
        self._hide_listening_popup()

    def _clear_screen(self):
        self.txt_in.text.delete("1.0", END)
        self.txt_out.text.delete("1.0", END)
        self.var_punctuation.set("")
        self.var_status.set("Screen cleared.")

    def _repeat_last_output(self):
        text = self.txt_out.text.get("1.0", END).strip()
        if not text:
            return
        _, _, out_tts = self._resolve_output_language()
        threading.Thread(target=engine.speak, args=(text,), kwargs={"lang": out_tts}, daemon=True).start()

    def _play_history_audio(self, text):
        if not text:
            return
        _, _, out_tts = self._resolve_output_language()
        threading.Thread(target=engine.speak, args=(text,), kwargs={"lang": out_tts}, daemon=True).start()

    def _shutdown(self):
        try:
            engine.stop_all()
        except Exception:
            pass
        self.destroy()

    def _play_input_audio(self):
        text = self.txt_in.text.get("1.0", END).strip()
        if not text:
            return
        in_name = self.var_in_lang.get()
        in_tts = config.LANGUAGES[in_name].get("tts", "en") 
        threading.Thread(target=engine.speak, args=(text,), kwargs={"lang": in_tts}, daemon=True).start()

    def _play_output_audio(self):
        text = self.txt_out.text.get("1.0", END).strip()
        if not text:
            return
        _, _, out_tts = self._resolve_output_language()
        threading.Thread(target=engine.speak, args=(text,), kwargs={"lang": out_tts}, daemon=True).start()

if __name__ == "__main__":
    app = ModernVoiceApp()
    app.mainloop()