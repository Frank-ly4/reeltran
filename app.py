import subprocess
import sys
import os
import re
from datetime import datetime

# --- 1. PREVENT WINDOWLESS CRASHES ---
class DummyWriter:
    def write(self, x):
        pass

    def flush(self):
        pass


if sys.stdout is None:
    sys.stdout = DummyWriter()
if sys.stderr is None:
    sys.stderr = DummyWriter()

# --- 2. SET UP PATHS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + current_dir
SAVED_FOLDER = os.path.join(current_dir, "SavedText")
os.makedirs(SAVED_FOLDER, exist_ok=True)

# --- 3. AUTO-DEPENDENCY INSTALLER ---
def ensure_dependencies():
    package_to_module = {
        "yt-dlp": "yt_dlp",
        "openai": "openai",
        "customtkinter": "customtkinter",
    }

    for package_name, module_name in package_to_module.items():
        try:
            __import__(module_name)
        except ImportError:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                capture_output=True,
                text=True,
            )


ensure_dependencies()

# --- 4. MAIN APPLICATION ---
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import yt_dlp
from openai import OpenAI

# ===== CONSTANTS =====
TRANSCRIPTION_MODEL = "whisper-1"
TRANSLATION_MODEL = "gpt-4o"

LANGUAGE_MAP = {
    "Autodetect": None,
    "Spanish": "es",
    "French": "fr",
    "Japanese": "ja",
    "Korean": "ko",
    "Hindi": "hi",
    "Mandarin Chinese": "zh",
    "Thai": "th",
    "Cambodian": "km",
    "Italian": "it",
    "German": "de",
    "Vietnamese": "vi",
    "Arabic": "ar",
    "Russian": "ru",
}

OUTPUT_LANGUAGE_OPTIONS = [
    "English",
    "Spanish",
    "French",
    "Japanese",
    "Korean",
    "Hindi",
    "Mandarin Chinese",
    "Thai",
    "Cambodian",
    "Italian",
    "German",
    "Vietnamese",
    "Arabic",
    "Russian",
    "Portuguese",
]

CODE_TO_LANGUAGE = {v: k for k, v in LANGUAGE_MAP.items() if v}

THEMES = {
    "Midnight": {
        "transparent_bg": "#010203",
        "bg": "#0b0d12",
        "card": "#11141d",
        "card_2": "#151927",
        "border": "#242938",
        "text": "#f3f4f6",
        "text_muted": "#9ca3af",
        "accent": "#4f46e5",
        "accent_hover": "#5b52f1",
        "unselected": "#1a1f2b",
        "unselected_hover": "#222838",
        "input_bg": "#0f1320",
        "progress_bg": "#1a1f2b",
        "danger_hover": "#c0392b",
    },
    "Pastel": {
        "transparent_bg": "#010203",
        "bg": "#f6f0ff",
        "card": "#fff7fd",
        "card_2": "#f8ebff",
        "border": "#d9c8f5",
        "text": "#3f2d56",
        "text_muted": "#7b6a91",
        "accent": "#b694ff",
        "accent_hover": "#a77dfc",
        "unselected": "#f1e4ff",
        "unselected_hover": "#ead9ff",
        "input_bg": "#fffaff",
        "progress_bg": "#ead9ff",
        "danger_hover": "#d65b7a",
    },
    "Slate": {
        "transparent_bg": "#010203",
        "bg": "#111827",
        "card": "#172033",
        "card_2": "#1e293b",
        "border": "#334155",
        "text": "#f8fafc",
        "text_muted": "#94a3b8",
        "accent": "#0ea5e9",
        "accent_hover": "#38bdf8",
        "unselected": "#243144",
        "unselected_hover": "#304257",
        "input_bg": "#0f172a",
        "progress_bg": "#243144",
        "danger_hover": "#dc2626",
    },
    "Forest": {
        "transparent_bg": "#010203",
        "bg": "#0c1511",
        "card": "#12201a",
        "card_2": "#162821",
        "border": "#244034",
        "text": "#eefbf2",
        "text_muted": "#93b39c",
        "accent": "#2fbf71",
        "accent_hover": "#36d37e",
        "unselected": "#1a2e26",
        "unselected_hover": "#223a31",
        "input_bg": "#0f1a15",
        "progress_bg": "#1a2e26",
        "danger_hover": "#c0392b",
    },
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ReelTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1280x840")
        self.root.minsize(1080, 720)

        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.last_processed_url = ""

        self.theme_name_var = tk.StringVar(value="Midnight")
        self.language_var = tk.StringVar(value="Autodetect")
        self.output_language_var = tk.StringVar(value="English")
        self.language_buttons = {}

        self.theme = THEMES[self.theme_name_var.get()]
        self.is_maximized = False
        self.was_minimized = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.normal_geometry = "1280x840+100+60"
        self.rounded_window_enabled = False

        self._configure_root_window()
        self._build_ui()
        self.apply_theme(self.theme_name_var.get())

        self.root.after(50, self._enable_custom_window)
        self.root.bind("<Map>", self._on_window_map)

    # ---------------- Window shell ---------------- #
    def _configure_root_window(self):
        self.root.title("Reel Translator")
        try:
            if sys.platform.startswith("win"):
                self.root.config(bg=self.theme["transparent_bg"])
                self.root.wm_attributes("-transparentcolor", self.theme["transparent_bg"])
                self.rounded_window_enabled = True
        except Exception:
            self.rounded_window_enabled = False

    def _enable_custom_window(self):
        try:
            self.root.overrideredirect(True)
        except Exception:
            pass

    def _on_window_map(self, event=None):
        if self.was_minimized:
            self.root.after(10, self._enable_custom_window)
            self.was_minimized = False

    def start_move(self, event):
        if self.is_maximized:
            return
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def do_move(self, event):
        if self.is_maximized:
            return
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    def minimize_window(self):
        self.was_minimized = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def close_window(self):
        self.root.destroy()

    def toggle_maximize(self, event=None):
        if not self.is_maximized:
            self.normal_geometry = self.root.geometry()
            x, y, w, h = self.get_work_area()
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.is_maximized = True
            self.max_button.configure(text="❐")
        else:
            self.root.geometry(self.normal_geometry)
            self.is_maximized = False
            self.max_button.configure(text="□")

    def get_work_area(self):
        if sys.platform.startswith("win"):
            try:
                import ctypes
                from ctypes import wintypes

                SPI_GETWORKAREA = 48
                rect = wintypes.RECT()
                ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
                )
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
            except Exception:
                pass

        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    # ---------------- UI ---------------- #
    def _build_ui(self):
        self.main_container = ctk.CTkFrame(
            self.root,
            corner_radius=28,
            border_width=1,
        )
        self.main_container.pack(fill="both", expand=True, padx=8, pady=8)

        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=4)
        self.main_container.grid_columnconfigure(1, weight=1)

        self._build_top_bar()
        self._build_workspace_panel()
        self._build_right_column()

    def _build_top_bar(self):
        self.top_bar = ctk.CTkFrame(
            self.main_container,
            height=42,
            corner_radius=18,
            fg_color="transparent",
        )
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))
        self.top_bar.grid_columnconfigure(0, weight=1)

        self.drag_area = ctk.CTkFrame(self.top_bar, fg_color="transparent", height=32, corner_radius=0)
        self.drag_area.grid(row=0, column=0, sticky="ew")

        for widget in (self.top_bar, self.drag_area):
            widget.bind("<Button-1>", self.start_move)
            widget.bind("<B1-Motion>", self.do_move)
            widget.bind("<Double-Button-1>", self.toggle_maximize)

        self.title_controls = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.title_controls.grid(row=0, column=1, sticky="e")

        self.theme_menu = ctk.CTkOptionMenu(
            self.title_controls,
            values=list(THEMES.keys()),
            variable=self.theme_name_var,
            command=self.apply_theme,
            width=140,
            height=34,
            corner_radius=12,
        )
        self.theme_menu.pack(side="left", padx=(0, 10))

        self.min_button = ctk.CTkButton(
            self.title_controls,
            text="—",
            width=34,
            height=34,
            corner_radius=10,
            command=self.minimize_window,
        )
        self.min_button.pack(side="left", padx=3)

        self.max_button = ctk.CTkButton(
            self.title_controls,
            text="□",
            width=34,
            height=34,
            corner_radius=10,
            command=self.toggle_maximize,
        )
        self.max_button.pack(side="left", padx=3)

        self.close_button = ctk.CTkButton(
            self.title_controls,
            text="✕",
            width=34,
            height=34,
            corner_radius=10,
            command=self.close_window,
        )
        self.close_button.pack(side="left", padx=(3, 0))

    def _build_workspace_panel(self):
        self.workspace_panel = ctk.CTkFrame(
            self.main_container,
            corner_radius=24,
            border_width=1,
        )
        self.workspace_panel.grid(row=1, column=0, sticky="nsew", padx=(10, 7), pady=(4, 10))
        self.workspace_panel.grid_rowconfigure(2, weight=1)
        self.workspace_panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.workspace_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w")

        self.title_label = ctk.CTkLabel(
            title_block,
            text="Transcript Workspace",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_block,
            text="Hosted transcription + nuanced translation",
            font=ctk.CTkFont(size=13),
        )
        self.subtitle_label.pack(anchor="w", pady=(3, 0))

        actions_block = ctk.CTkFrame(header, fg_color="transparent")
        actions_block.grid(row=0, column=1, sticky="e")

        self.save_btn = ctk.CTkButton(
            actions_block,
            text="Save Output",
            width=120,
            height=38,
            corner_radius=12,
            state="disabled",
            command=self.save_to_file,
        )
        self.save_btn.pack(side="right")

        self.status_frame = ctk.CTkFrame(
            self.workspace_panel,
            corner_radius=18,
            border_width=1,
            height=78,
        )
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
        self.status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Ready",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.status_hint = ctk.CTkLabel(
            self.status_frame,
            text="Paste a clip URL below and process when ready.",
            font=ctk.CTkFont(size=12),
        )
        self.status_hint.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(
            self.status_frame,
            corner_radius=100,
            height=10,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.progress_bar.set(0)

        self.output_wrapper = ctk.CTkFrame(
            self.workspace_panel,
            corner_radius=20,
            border_width=1,
        )
        self.output_wrapper.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 14))
        self.output_wrapper.grid_rowconfigure(0, weight=1)
        self.output_wrapper.grid_columnconfigure(0, weight=1)

        self.output_area = ctk.CTkTextbox(
            self.output_wrapper,
            wrap="word",
            font=ctk.CTkFont(family="Consolas", size=15),
            corner_radius=18,
            border_width=0,
            activate_scrollbars=True,
        )
        self.output_area.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.output_area.insert("1.0", "Your bilingual transcript will appear here.\n")
        self.output_area.configure(state="disabled")

        self.bottom_bar = ctk.CTkFrame(
            self.workspace_panel,
            corner_radius=18,
            border_width=1,
            height=84,
        )
        self.bottom_bar.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        self.bottom_bar.grid_columnconfigure(0, weight=1)

        self.url_label = ctk.CTkLabel(
            self.bottom_bar,
            text="Clip URL",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.url_label.grid(row=0, column=0, sticky="w", padx=16, pady=(10, 4), columnspan=2)

        self.url_entry = ctk.CTkEntry(
            self.bottom_bar,
            height=44,
            corner_radius=14,
            placeholder_text="Paste Reel or YouTube URL here...",
        )
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=(16, 10), pady=(0, 14))

        self.process_btn = ctk.CTkButton(
            self.bottom_bar,
            text="Process Reel",
            width=150,
            height=44,
            corner_radius=14,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_processing,
        )
        self.process_btn.grid(row=1, column=1, sticky="e", padx=(0, 16), pady=(0, 14))

    def _build_right_column(self):
        self.right_column = ctk.CTkFrame(
            self.main_container,
            fg_color="transparent",
            corner_radius=0,
        )
        self.right_column.grid(row=1, column=1, sticky="nsew", padx=(7, 10), pady=(4, 10))
        self.right_column.grid_rowconfigure(0, weight=3)
        self.right_column.grid_rowconfigure(1, weight=1)
        self.right_column.grid_columnconfigure(0, weight=1)

        # Source language panel
        self.source_panel = ctk.CTkFrame(
            self.right_column,
            corner_radius=24,
            border_width=1,
        )
        self.source_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.source_panel.grid_rowconfigure(1, weight=1)
        self.source_panel.grid_columnconfigure(0, weight=1)

        source_top = ctk.CTkFrame(self.source_panel, fg_color="transparent")
        source_top.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

        self.lang_title = ctk.CTkLabel(
            source_top,
            text="Source Language",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.lang_title.pack(anchor="w")

        self.lang_subtitle = ctk.CTkLabel(
            source_top,
            text="Select one option. Backend behavior stays the same.",
            font=ctk.CTkFont(size=12),
            justify="left",
            wraplength=240,
        )
        self.lang_subtitle.pack(anchor="w", pady=(4, 0))

        self.language_list = ctk.CTkScrollableFrame(
            self.source_panel,
            corner_radius=18,
            border_width=1,
        )
        self.language_list.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))

        for language_name in LANGUAGE_MAP.keys():
            btn = ctk.CTkButton(
                self.language_list,
                text=language_name,
                anchor="w",
                height=42,
                corner_radius=12,
                command=lambda name=language_name: self.select_language(name),
            )
            btn.pack(fill="x", pady=5, padx=6)
            self.language_buttons[language_name] = btn

        self.selection_badge = ctk.CTkLabel(
            self.source_panel,
            text="Selected: Autodetect",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.selection_badge.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))

        # Output language panel
        self.output_panel = ctk.CTkFrame(
            self.right_column,
            corner_radius=24,
            border_width=1,
        )
        self.output_panel.grid(row=1, column=0, sticky="nsew")
        self.output_panel.grid_columnconfigure(0, weight=1)

        output_top = ctk.CTkFrame(self.output_panel, fg_color="transparent")
        output_top.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

        self.output_title = ctk.CTkLabel(
            output_top,
            text="Output Language",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.output_title.pack(anchor="w")

        self.output_subtitle = ctk.CTkLabel(
            output_top,
            text="Choose the target translation language.",
            font=ctk.CTkFont(size=12),
            justify="left",
            wraplength=240,
        )
        self.output_subtitle.pack(anchor="w", pady=(4, 10))

        self.output_language_menu = ctk.CTkOptionMenu(
            self.output_panel,
            values=OUTPUT_LANGUAGE_OPTIONS,
            variable=self.output_language_var,
            width=220,
            height=42,
            corner_radius=12,
        )
        self.output_language_menu.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        self.output_badge = ctk.CTkLabel(
            self.output_panel,
            text="Target: English",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.output_badge.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 16))

        self.output_language_var.trace_add("write", self._on_output_language_change)

    def _on_output_language_change(self, *args):
        self.output_badge.configure(text=f"Target: {self.output_language_var.get()}")

    def select_language(self, language_name: str):
        self.language_var.set(language_name)
        self.selection_badge.configure(text=f"Selected: {language_name}")
        self.update_language_button_states()

    def update_language_button_states(self):
        selected = self.language_var.get()
        for name, button in self.language_buttons.items():
            if name == selected:
                button.configure(
                    fg_color=self.theme["accent"],
                    hover_color=self.theme["accent_hover"],
                    text_color="white",
                )
            else:
                button.configure(
                    fg_color=self.theme["unselected"],
                    hover_color=self.theme["unselected_hover"],
                    text_color=self.theme["text"],
                )

    def apply_theme(self, theme_name=None):
        if theme_name is not None:
            self.theme_name_var.set(theme_name)

        self.theme = THEMES[self.theme_name_var.get()]
        t = self.theme

        try:
            if self.rounded_window_enabled:
                self.root.config(bg=t["transparent_bg"])
        except Exception:
            pass

        self.main_container.configure(fg_color=t["bg"], border_color=t["border"])
        self.top_bar.configure(fg_color="transparent")
        self.drag_area.configure(fg_color="transparent")

        self.theme_menu.configure(
            fg_color=t["unselected"],
            button_color=t["accent"],
            button_hover_color=t["accent_hover"],
            text_color=t["text"],
            dropdown_fg_color=t["card_2"],
            dropdown_hover_color=t["unselected_hover"],
            dropdown_text_color=t["text"],
        )

        for btn in (self.min_button, self.max_button):
            btn.configure(
                fg_color=t["unselected"],
                hover_color=t["unselected_hover"],
                text_color=t["text"],
            )
        self.close_button.configure(
            fg_color=t["unselected"],
            hover_color=t["danger_hover"],
            text_color=t["text"],
        )

        self.workspace_panel.configure(fg_color=t["card"], border_color=t["border"])
        self.title_label.configure(text_color=t["text"])
        self.subtitle_label.configure(text_color=t["text_muted"])

        self.save_btn.configure(
            fg_color=t["unselected"],
            hover_color=t["unselected_hover"],
            text_color=t["text"],
        )

        self.status_frame.configure(fg_color=t["card_2"], border_color=t["border"])
        self.status_label.configure(text_color=t["text"])
        self.status_hint.configure(text_color=t["text_muted"])
        self.progress_bar.configure(fg_color=t["progress_bg"], progress_color=t["accent"])

        self.output_wrapper.configure(fg_color=t["input_bg"], border_color=t["border"])
        self.output_area.configure(
            fg_color=t["input_bg"],
            text_color=t["text"],
            scrollbar_button_color=t["unselected"],
            scrollbar_button_hover_color=t["unselected_hover"],
        )

        self.bottom_bar.configure(fg_color=t["card_2"], border_color=t["border"])
        self.url_label.configure(text_color=t["text_muted"])
        self.url_entry.configure(
            fg_color=t["input_bg"],
            border_color=t["border"],
            text_color=t["text"],
            placeholder_text_color=t["text_muted"],
        )
        self.process_btn.configure(
            fg_color=t["accent"],
            hover_color=t["accent_hover"],
            text_color="white",
        )

        self.source_panel.configure(fg_color=t["card"], border_color=t["border"])
        self.lang_title.configure(text_color=t["text"])
        self.lang_subtitle.configure(text_color=t["text_muted"])
        self.language_list.configure(fg_color=t["card_2"], border_color=t["border"])
        self.selection_badge.configure(text_color=t["text_muted"])

        self.output_panel.configure(fg_color=t["card"], border_color=t["border"])
        self.output_title.configure(text_color=t["text"])
        self.output_subtitle.configure(text_color=t["text_muted"])
        self.output_badge.configure(text_color=t["text_muted"])
        self.output_language_menu.configure(
            fg_color=t["unselected"],
            button_color=t["accent"],
            button_hover_color=t["accent_hover"],
            text_color=t["text"],
            dropdown_fg_color=t["card_2"],
            dropdown_hover_color=t["unselected_hover"],
            dropdown_text_color=t["text"],
        )

        self.update_language_button_states()

    # ---------------- Helpers ---------------- #
    def display_language_name(self, lang_value):
        if not lang_value:
            return "Autodetect"
        if lang_value in CODE_TO_LANGUAGE:
            return CODE_TO_LANGUAGE[lang_value]
        return str(lang_value)

    def set_status(self, text, progress=None, hint=None):
        self.root.after(0, lambda: self.status_label.configure(text=text))
        if hint is not None:
            self.root.after(0, lambda: self.status_hint.configure(text=hint))
        if progress is not None:
            self.root.after(0, lambda: self.progress_bar.set(progress / 100.0))

    def clear_output(self):
        def _clear():
            self.output_area.configure(state="normal")
            self.output_area.delete("1.0", "end")
            self.output_area.configure(state="disabled")

        self.root.after(0, _clear)

    def log_message(self, message: str = ""):
        def _write():
            self.output_area.configure(state="normal")
            self.output_area.insert("end", message + "\n")
            self.output_area.see("end")
            self.output_area.configure(state="disabled")

        self.root.after(0, _write)

    # ---------------- Workflow entry ---------------- #
    def start_processing(self):
        if not self.client:
            messagebox.showerror(
                "API Key Missing",
                "Please set your OpenAI API key in the OPENAI_API_KEY environment variable.",
            )
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please paste a Reel or YouTube URL first.")
            return

        self.last_processed_url = url
        selected_language = self.language_var.get()
        target_language = self.output_language_var.get()

        self.process_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.clear_output()
        self.set_status(
            "Working...",
            0,
            f"Downloading, transcribing, and translating to {target_language}.",
        )

        threading.Thread(
            target=self.process_video,
            args=(url, selected_language, target_language),
            daemon=True,
        ).start()

    # ---------------- GPT translation ---------------- #
    def translate_segments_with_gpt(self, source_segments, target_language):
        if not source_segments:
            return {}

        prompt_text = "\n".join(f"{i+1}. {text}" for i, text in enumerate(source_segments))
        system_msg = (
            f"You are a professional translator. "
            f"You will receive a numbered list of transcript segments. "
            f"Translate each into natural, nuanced {target_language} while preserving tone, slang, emotion, and meaning. "
            f"Return ONLY the translated numbered list. Do not add notes or commentary."
        )

        try:
            response = self.client.chat.completions.create(
                model=TRANSLATION_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.3,
            )
            output = response.choices[0].message.content.strip()

            translated = {}
            for line in output.splitlines():
                match = re.match(r"^(\d+)\.\s*(.*)", line.strip())
                if match:
                    translated[int(match.group(1)) - 1] = match.group(2).strip()
            return translated
        except Exception as e:
            self.log_message(f"❌ Translation error: {e}")
            return {}

    # ---------------- Main processing ---------------- #
    def process_video(self, url: str, selected_language: str, target_language: str):
        timestamp = datetime.now().strftime("%H%M%S")
        audio_filename = f"temp_audio_{timestamp}.mp3"

        try:
            # STEP 1: Download audio
            self.set_status("Downloading audio...", 15, "Fetching and extracting the clip audio.")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": audio_filename.replace(".mp3", ""),
                "ffmpeg_location": current_dir,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "quiet": True,
                "noprogress": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # STEP 2: Hosted segmented transcription
            self.set_status("Transcribing...", 60, "Running hosted transcription on the audio.")
            language_code = LANGUAGE_MAP.get(selected_language)

            transcription_kwargs = {
                "model": TRANSCRIPTION_MODEL,
                "response_format": "verbose_json",
            }
            if language_code:
                transcription_kwargs["language"] = language_code

            with open(audio_filename, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    file=audio_file,
                    **transcription_kwargs,
                )

            transcript_text = getattr(transcript, "text", "") or ""
            segments = getattr(transcript, "segments", None) or []

            usable_segments = []
            source_texts = []

            for seg in segments:
                if isinstance(seg, dict):
                    text = seg.get("text", "")
                else:
                    text = getattr(seg, "text", "")

                text = (text or "").strip()
                if len(text) >= 1:
                    # Split by newlines to create line-by-line segments
                    lines = text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:  # Only add non-empty lines
                            usable_segments.append({"text": line})
                            source_texts.append(line)

            if not usable_segments and transcript_text.strip():
                # Split transcript_text by newlines too
                lines = transcript_text.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        usable_segments.append({"text": line})
                        source_texts.append(line)

            if not source_texts:
                raise ValueError("No transcription text was returned.")

            # STEP 3: Translate
            self.set_status(
                "Translating...",
                85,
                f"Turning the transcript into natural {target_language}.",
            )
            translated = self.translate_segments_with_gpt(source_texts, target_language)

            detected_language = self.display_language_name(getattr(transcript, "language", None))
            if detected_language == "Autodetect" and selected_language != "Autodetect":
                detected_language = selected_language

            # STEP 4: Display output
            header = (
                f"TRANSCRIPTION ({detected_language} → {target_language}) | "
                f"{datetime.now():%Y-%m-%d %H:%M} | URL: {url}"
            )
            self.log_message(header)
            self.log_message("=" * 80)

            for i, seg in enumerate(usable_segments):
                original_text = seg['text']
                translated_text = translated.get(i, '[translation unavailable]')
                self.log_message(f"{original_text}")
                self.log_message(f"{translated_text}")
                self.log_message("")

            self.log_message("=" * 80)
            self.log_message("✅ Finished!")

            self.set_status("Done!", 100, f"Transcript and {target_language} translation are ready.")
            self.root.after(0, lambda: self.save_btn.configure(state="normal"))

        except Exception as e:
            self.log_message(f"\n❌ Error: {e}")
            self.set_status("Error occurred.", 0, "Something went wrong while processing the clip.")
        finally:
            if os.path.exists(audio_filename):
                try:
                    os.remove(audio_filename)
                except Exception:
                    pass

            self.root.after(0, lambda: self.process_btn.configure(state="normal"))

    # ---------------- Save output ---------------- #
    def save_to_file(self):
        content = self.output_area.get("1.0", "end").strip()
        if not content:
            return

        fname = f"Reel_{datetime.now():%Y-%m-%d_%H%M}.txt"
        path = filedialog.asksaveasfilename(
            initialdir=SAVED_FOLDER,
            initialfile=fname,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )

        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Success", "File saved!")


if __name__ == "__main__":
    root = ctk.CTk()
    app = ReelTranslatorApp(root)
    root.mainloop()