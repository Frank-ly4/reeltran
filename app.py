import subprocess
import sys
import os
import time
import re
from datetime import datetime

# --- 1. PREVENT WINDOWLESS CRASHES ---
class DummyWriter:
    def write(self, x): pass
    def flush(self): pass

if sys.stdout is None: sys.stdout = DummyWriter()
if sys.stderr is None: sys.stderr = DummyWriter()

# --- 2. SET UP PATHS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] += os.pathsep + current_dir
SAVED_FOLDER = os.path.join(current_dir, "SavedText")
if not os.path.exists(SAVED_FOLDER):
    os.makedirs(SAVED_FOLDER)

# --- 3. AUTO-DEPENDENCY INSTALLER ---
def ensure_dependencies():
    required_libs = ["yt-dlp", "openai-whisper", "openai"]
    for lib in required_libs:
        try:
            if lib == "openai-whisper":
                import whisper  # noqa: F401
            else:
                __import__(lib)
        except ImportError:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", lib], capture_output=True
            )

ensure_dependencies()

# --- 4. MAIN APPLICATION ---
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import threading
import yt_dlp
import whisper
from openai import OpenAI

# =====  CONSTANTS  =========================================================
GPT_MODEL = "gpt-4o"  # easy to A/B-test later (e.g. "gpt-4o" vs "gpt-4.1")

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

# ===========================================================================
class ReelTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reel Translator (Whisper-Turbo + GPT)")
        self.root.geometry("900x820")
        self.root.resizable(True, True)

        # Initialise OpenAI client safely
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.whisper_model = None

        self._build_ui()

    # ---------------- UI ---------------- #
    def _build_ui(self):
        # URL Input row
        input_frame = tk.Frame(self.root, pady=8)
        input_frame.pack(fill=tk.X, padx=20)
        tk.Label(input_frame, text="Reel URL:", font=("Arial", 11)).pack(side=tk.LEFT)
        self.url_entry = tk.Entry(input_frame, font=("Arial", 11), width=55)
        self.url_entry.pack(side=tk.LEFT, padx=10)
        self.process_btn = tk.Button(
            input_frame,
            text="Process Reel",
            font=("Arial", 10, "bold"),
            bg="#007bff",
            fg="white",
            command=self.start_processing,
        )
        self.process_btn.pack(side=tk.LEFT)

        # Language dropdown row
        lang_frame = tk.Frame(self.root, pady=2)
        lang_frame.pack(fill=tk.X, padx=20)
        tk.Label(lang_frame, text="Source language:", font=("Arial", 11)).pack(
            side=tk.LEFT
        )
        self.language_var = tk.StringVar(value="Autodetect")
        self.lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.language_var,
            values=list(LANGUAGE_MAP.keys()),
            state="readonly",
            width=22,
        )
        self.lang_combo.pack(side=tk.LEFT, padx=10)

        # Status & Progress
        status_frame = tk.Frame(self.root, pady=5)
        status_frame.pack(fill=tk.X, padx=20)
        self.status_label = tk.Label(
            status_frame, text="Ready", font=("Arial", 10, "italic"), fg="#555"
        )
        self.status_label.pack(side=tk.LEFT)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.root, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill=tk.X, padx=20, pady=(0, 10))

        # Output area
        self.output_area = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, font=("Consolas", 11), height=26
        )
        self.output_area.pack(fill=tk.BOTH, padx=20, pady=5)

        # Save button
        self.save_btn = tk.Button(
            self.root,
            text="Save to SavedText Folder",
            font=("Arial", 11),
            command=self.save_to_file,
            state=tk.DISABLED,
        )
        self.save_btn.pack(pady=10)

    # ------------- Convenience helpers ------------- #
    def set_status(self, text, progress=None):
        self.root.after(0, lambda: self.status_label.config(text=text))
        if progress is not None:
            self.root.after(0, lambda: self.progress_var.set(progress))

    def log_message(self, message: str):
        self.root.after(0, lambda: self.output_area.insert(tk.END, message + "\n"))
        self.root.after(0, lambda: self.output_area.see(tk.END))

    # ------------- Workflow entrypoint ------------- #
    def start_processing(self):
        if not self.client:
            messagebox.showerror(
                "API Key Missing",
                "Please set your OpenAI API key in the OPENAI_API_KEY environment variable.",
            )
            return

        url = self.url_entry.get().strip()
        if not url:
            return

        self.process_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.output_area.delete(1.0, tk.END)
        threading.Thread(target=self.process_video, args=(url,), daemon=True).start()

    # ------------- GPT-4 Batch Translation ------------- #
    def translate_batch_with_gpt(self, source_segments):
        """Translate all segments in one GPT request for speed & coherence."""
        if not source_segments:
            return {}

        # Format numbered list
        prompt_text = "\n".join(f"{i+1}. {txt}" for i, txt in enumerate(source_segments))

        system_msg = (
            "You are a professional foreign-language-to-English translator. "
            "You will receive a numbered list of transcript segments. "
            "Translate each into flowing, natural English, preserving slang and nuance. "
            "CRITICAL: Return ONLY the translated numbered list. "
            "Do NOT add any extra text."
        )

        try:
            response = self.client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.3,
            )
            output = response.choices[0].message.content.strip()

            # Parse back into {index: text}
            translated = {}
            for line in output.splitlines():
                m = re.match(r"^(\d+)\.\s*(.*)", line.strip())
                if m:
                    translated[int(m.group(1)) - 1] = m.group(2)
            return translated

        except Exception as e:
            self.log_message(f"❌ Translation error: {e}")
            return {}

    # ------------- Main processing chain ------------- #
    def process_video(self, url: str):
        timestamp = datetime.now().strftime("%H%M%S")
        audio_filename = f"temp_audio_{timestamp}.mp3"

        try:
            # STEP 1: Download audio
            self.set_status("⏳ Downloading audio...", 15)
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

            # STEP 2: Load Whisper-turbo model (lazy-load once)
            self.set_status("⏳ Loading Whisper turbo...", 35)
            if self.whisper_model is None:
                self.whisper_model = whisper.load_model("turbo")

            # STEP 3: Transcribe
            self.set_status("⏳ Transcribing (local)...", 60)
            selected_display = self.language_var.get()
            language_code = LANGUAGE_MAP[selected_display]

            if language_code:
                result = self.whisper_model.transcribe(
                    audio_filename,
                    language=language_code,
                    fp16=False,
                    condition_on_previous_text=True,
                )
            else:
                result = self.whisper_model.transcribe(
                    audio_filename,
                    fp16=False,
                    condition_on_previous_text=True,
                )
                language_code = result.get("language", "unknown")

            # Collect usable segments
            valid_segments, source_texts = [], []
            for seg in result["segments"]:
                text = seg["text"].strip()
                if len(text) >= 2:  # skip tiny noise blips
                    valid_segments.append(seg)
                    source_texts.append(text)

            # STEP 4: Batch translate
            self.set_status("⏳ Translating with GPT...", 85)
            translated = self.translate_batch_with_gpt(source_texts)

            # STEP 5: Display output
            header_lang = (
                selected_display if selected_display != "Autodetect" else language_code
            )
            self.log_message(
                f"TRANSCRIPTION ({header_lang})  {datetime.now():%Y-%m-%d %H:%M}\n"
                + "=" * 50
            )
            for i, seg in enumerate(valid_segments):
                t_range = f"[{seg['start']:.1f}s – {seg['end']:.1f}s]"
                src = source_texts[i]
                en = translated.get(i, "[translation missing]")
                self.log_message(f"{t_range}\nSRC: {src}\nEN:  {en}\n")

            self.log_message("=" * 50 + "\n✅ Finished!")
            self.set_status("Done!", 100)
            self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))

        except Exception as e:
            self.log_message(f"\n❌ Error: {e}")
            self.set_status("Error occurred.", 0)
        finally:
            if os.path.exists(audio_filename):
                try:
                    os.remove(audio_filename)
                except Exception:
                    pass
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))

    # ------------- Save output ------------- #
    def save_to_file(self):
        content = self.output_area.get(1.0, tk.END).strip()
        if not content:
            return
        fname = f"Reel_{datetime.now():%Y-%m-%d_%H%M}.txt"
        path = filedialog.asksaveasfilename(
            initialdir=SAVED_FOLDER,
            initialfile=fname,
            defaultextension=".txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Success", "File saved!")

# ------------------- RUN ------------------- #
if __name__ == "__main__":
    root = tk.Tk()
    app = ReelTranslatorApp(root)
    root.mainloop()