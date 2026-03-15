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
TRANSCRIPTION_MODEL = "gpt-4o-transcribe-diarize"
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

# ===== THEME =====
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG = "#0b0d12"
CARD = "#11141d"
CARD_2 = "#151927"
BORDER = "#242938"
TEXT = "#f3f4f6"
TEXT_MUTED = "#9ca3af"
ACCENT = "#4f46e5"
ACCENT_HOVER = "#5b52f1"
UNSELECTED = "#1a1f2b"
UNSELECTED_HOVER = "#222838"
INPUT_BG = "#0f1320"
PROGRESS_BG = "#1a1f2b"


class ReelTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reel Translator")
        self.root.geometry("1280x820")
        self.root.minsize(1080, 700)

        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.last_processed_url = ""

        self.language_var = tk.StringVar(value="Autodetect")
        self.language_buttons = {}

        self._build_ui()

    # ---------------- UI ---------------- #
    def _build_ui(self):
        self.root.configure(bg=BG)

        self.main_shell = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.main_shell.pack(fill="both", expand=True, padx=18, pady=18)

        self.main_shell.grid_columnconfigure(0, weight=4)
        self.main_shell.grid_columnconfigure(1, weight=1)
        self.main_shell.grid_rowconfigure(0, weight=1)

        self._build_workspace_panel()
        self._build_language_panel()

    def _build_workspace_panel(self):
        self.workspace_panel = ctk.CTkFrame(
            self.main_shell,
            fg_color=CARD,
            corner_radius=24,
            border_width=1,
            border_color=BORDER,
        )
        self.workspace_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=0)

        self.workspace_panel.grid_rowconfigure(2, weight=1)
        self.workspace_panel.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self.workspace_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w")

        self.title_label = ctk.CTkLabel(
            title_block,
            text="Transcript Workspace",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT,
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_block,
            text="Hosted transcription + nuanced English translation",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_MUTED,
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
            fg_color=UNSELECTED,
            hover_color=UNSELECTED_HOVER,
            text_color=TEXT,
            state="disabled",
            command=self.save_to_file,
        )
        self.save_btn.pack(side="right")

        # Status + progress
        status_frame = ctk.CTkFrame(
            self.workspace_panel,
            fg_color=CARD_2,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
            height=78,
        )
        status_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT,
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.status_hint = ctk.CTkLabel(
            status_frame,
            text="Paste a clip URL below and process when ready.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        )
        self.status_hint.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(
            status_frame,
            progress_color=ACCENT,
            fg_color=PROGRESS_BG,
            corner_radius=100,
            height=10,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.progress_bar.set(0)

        # Output area
        output_wrapper = ctk.CTkFrame(
            self.workspace_panel,
            fg_color=INPUT_BG,
            corner_radius=20,
            border_width=1,
            border_color=BORDER,
        )
        output_wrapper.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 14))
        output_wrapper.grid_rowconfigure(0, weight=1)
        output_wrapper.grid_columnconfigure(0, weight=1)

        self.output_area = ctk.CTkTextbox(
            output_wrapper,
            wrap="word",
            font=ctk.CTkFont(family="Consolas", size=15),
            text_color=TEXT,
            fg_color=INPUT_BG,
            corner_radius=18,
            border_width=0,
            activate_scrollbars=True,
        )
        self.output_area.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.output_area.insert("1.0", "Your bilingual transcript will appear here.\n")
        self.output_area.configure(state="disabled")

        # Bottom URL bar
        bottom_bar = ctk.CTkFrame(
            self.workspace_panel,
            fg_color=CARD_2,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
            height=82,
        )
        bottom_bar.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom_bar.grid_columnconfigure(0, weight=1)

        url_label = ctk.CTkLabel(
            bottom_bar,
            text="Clip URL",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MUTED,
        )
        url_label.grid(row=0, column=0, sticky="w", padx=16, pady=(10, 4), columnspan=2)

        self.url_entry = ctk.CTkEntry(
            bottom_bar,
            height=44,
            corner_radius=14,
            fg_color=INPUT_BG,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text="Paste Reel or YouTube URL here...",
        )
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=(16, 10), pady=(0, 14))

        self.process_btn = ctk.CTkButton(
            bottom_bar,
            text="Process Reel",
            width=150,
            height=44,
            corner_radius=14,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_processing,
        )
        self.process_btn.grid(row=1, column=1, sticky="e", padx=(0, 16), pady=(0, 14))

    def _build_language_panel(self):
        self.language_panel = ctk.CTkFrame(
            self.main_shell,
            fg_color=CARD,
            corner_radius=24,
            border_width=1,
            border_color=BORDER,
        )
        self.language_panel.grid(row=0, column=1, sticky="nsew")

        self.language_panel.grid_rowconfigure(1, weight=1)
        self.language_panel.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self.language_panel, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))

        lang_title = ctk.CTkLabel(
            top,
            text="Source Language",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT,
        )
        lang_title.pack(anchor="w")

        lang_subtitle = ctk.CTkLabel(
            top,
            text="Select one option. Backend behavior stays the same.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=220,
        )
        lang_subtitle.pack(anchor="w", pady=(4, 0))

        self.language_list = ctk.CTkScrollableFrame(
            self.language_panel,
            fg_color=CARD_2,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        self.language_list.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 14))

        for language_name in LANGUAGE_MAP.keys():
            btn = ctk.CTkButton(
                self.language_list,
                text=language_name,
                anchor="w",
                height=42,
                corner_radius=12,
                fg_color=UNSELECTED,
                hover_color=UNSELECTED_HOVER,
                text_color=TEXT,
                font=ctk.CTkFont(size=13, weight="bold" if language_name == "Autodetect" else "normal"),
                command=lambda name=language_name: self.select_language(name),
            )
            btn.pack(fill="x", pady=5, padx=6)
            self.language_buttons[language_name] = btn

        self.selection_badge = ctk.CTkLabel(
            self.language_panel,
            text="Selected: Autodetect",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MUTED,
        )
        self.selection_badge.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 6))

        self.update_language_button_states()

    def select_language(self, language_name: str):
        self.language_var.set(language_name)
        self.selection_badge.configure(text=f"Selected: {language_name}")
        self.update_language_button_states()

    def update_language_button_states(self):
        selected = self.language_var.get()
        for name, button in self.language_buttons.items():
            if name == selected:
                button.configure(
                    fg_color=ACCENT,
                    hover_color=ACCENT_HOVER,
                    text_color="white",
                )
            else:
                button.configure(
                    fg_color=UNSELECTED,
                    hover_color=UNSELECTED_HOVER,
                    text_color=TEXT,
                )

    # ---------------- Helpers ---------------- #
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

        self.process_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.clear_output()
        self.set_status(
            "Working...",
            0,
            "Downloading audio, transcribing, and translating.",
        )

        threading.Thread(
            target=self.process_video,
            args=(url, selected_language),
            daemon=True,
        ).start()

    # ---------------- GPT translation ---------------- #
    def translate_segments_with_gpt(self, source_segments):
        if not source_segments:
            return {}

        prompt_text = "\n".join(f"{i+1}. {text}" for i, text in enumerate(source_segments))
        system_msg = (
            "You are a professional foreign-language-to-English translator. "
            "You will receive a numbered list of transcript segments. "
            "Translate each into natural, nuanced English while preserving tone, slang, emotion, and meaning. "
            "Return ONLY the translated numbered list. Do not add notes or commentary."
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
    def process_video(self, url: str, selected_language: str):
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
                "response_format": "diarized_json",
                "chunking_strategy": "auto",
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
                    usable_segments.append({"text": text})
                    source_texts.append(text)

            if not usable_segments and transcript_text.strip():
                usable_segments = [{"text": transcript_text.strip()}]
                source_texts = [transcript_text.strip()]

            if not source_texts:
                raise ValueError("No transcription text was returned.")

            # STEP 3: Translate
            self.set_status("Translating...", 85, "Turning the transcript into natural English.")
            translated = self.translate_segments_with_gpt(source_texts)

            detected_language = getattr(transcript, "language", None)
            if not detected_language and selected_language != "Autodetect":
                detected_language = selected_language
            elif not detected_language:
                detected_language = "Autodetect"

            # STEP 4: Display output
            header = (
                f"TRANSCRIPTION ({detected_language}) | {datetime.now():%Y-%m-%d %H:%M} | URL: {url}"
            )
            self.log_message(header)
            self.log_message("=" * 80)

            for i, seg in enumerate(usable_segments):
                self.log_message(f"Original: {seg['text']}")
                self.log_message(f"EN:  {translated.get(i, '[translation unavailable]')}")
                self.log_message("")

            self.log_message("=" * 80)
            self.log_message("✅ Finished!")

            self.set_status("Done!", 100, "Transcript and translation are ready.")
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