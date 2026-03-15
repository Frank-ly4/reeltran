import subprocess
import sys
import os
import re
import csv
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
LOG_FILE = os.path.join(current_dir, "clip_processing_log.csv")

os.makedirs(SAVED_FOLDER, exist_ok=True)

# --- 3. AUTO-DEPENDENCY INSTALLER ---
def ensure_dependencies():
    package_to_module = {
        "yt-dlp": "yt_dlp",
        "openai": "openai",
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
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import threading
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


def init_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "outcome",
                "stage",
                "url",
                "selected_language",
                "detected_language",
                "transcription_model",
                "translation_model",
                "error_type",
                "error_message",
            ])


def classify_error_message(message: str) -> str:
    msg = (message or "").lower()

    moderation_keywords = [
        "safety",
        "policy",
        "moderation",
        "content",
        "inappropriate",
        "not appropriate",
        "unsafe",
        "flagged",
        "disallowed",
        "blocked",
        "refused",
        "violation",
    ]

    if any(keyword in msg for keyword in moderation_keywords):
        return "POSSIBLE_SAFETY_BLOCK"

    return "ERROR"


class ReelTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reel Translator (Segmented Hosted Transcription + GPT-4o) [Logging]")
        self.root.geometry("920x840")
        self.root.resizable(True, True)

        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.last_processed_url = ""

        init_log_file()
        self._build_ui()

    # ---------------- UI ---------------- #
    def _build_ui(self):
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

        lang_frame = tk.Frame(self.root, pady=2)
        lang_frame.pack(fill=tk.X, padx=20)

        tk.Label(lang_frame, text="Source language:", font=("Arial", 11)).pack(side=tk.LEFT)

        self.language_var = tk.StringVar(value="Autodetect")
        self.lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.language_var,
            values=list(LANGUAGE_MAP.keys()),
            state="readonly",
            width=22,
        )
        self.lang_combo.pack(side=tk.LEFT, padx=10)

        status_frame = tk.Frame(self.root, pady=5)
        status_frame.pack(fill=tk.X, padx=20)

        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            font=("Arial", 10, "italic"),
            fg="#555",
        )
        self.status_label.pack(side=tk.LEFT)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=20, pady=(0, 10))

        self.output_area = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            font=("Consolas", 11),
            height=28,
        )
        self.output_area.pack(fill=tk.BOTH, padx=20, pady=5)

        self.save_btn = tk.Button(
            self.root,
            text="Save to SavedText Folder",
            font=("Arial", 11),
            command=self.save_to_file,
            state=tk.DISABLED,
        )
        self.save_btn.pack(pady=10)

    # ---------------- Helpers ---------------- #
    def set_status(self, text, progress=None):
        self.root.after(0, lambda: self.status_label.config(text=text))
        if progress is not None:
            self.root.after(0, lambda: self.progress_var.set(progress))

    def log_message(self, message: str = ""):
        self.root.after(0, lambda: self.output_area.insert(tk.END, message + "\n"))
        self.root.after(0, lambda: self.output_area.see(tk.END))

    def append_run_log(
        self,
        outcome,
        stage,
        url,
        selected_language,
        detected_language="",
        error_type="",
        error_message="",
    ):
        try:
            clean_error_message = (error_message or "").replace("\n", " ").replace("\r", " ").strip()
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    outcome,
                    stage,
                    url,
                    selected_language,
                    detected_language,
                    TRANSCRIPTION_MODEL,
                    TRANSLATION_MODEL,
                    error_type,
                    clean_error_message,
                ])
        except Exception:
            # Logging should never break the app flow
            pass

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
            messagebox.showwarning("Missing URL", "Please paste a Reel URL first.")
            return

        self.last_processed_url = url
        selected_language = self.language_var.get()

        self.process_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.output_area.delete(1.0, tk.END)

        self.append_run_log(
            outcome="STARTED",
            stage="start",
            url=url,
            selected_language=selected_language,
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

    # ---------------- Main processing ---------------- #
    def process_video(self, url: str, selected_language: str):
        timestamp = datetime.now().strftime("%H%M%S")
        audio_filename = f"temp_audio_{timestamp}.mp3"
        current_stage = "download"
        detected_language = ""

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

            # STEP 2: Hosted segmented transcription
            current_stage = "transcription"
            self.set_status("⏳ Transcribing with segmented hosted transcription...", 60)
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

            # Fallback if segments are unexpectedly missing
            if not usable_segments and transcript_text.strip():
                usable_segments = [{"text": transcript_text.strip()}]
                source_texts = [transcript_text.strip()]

            if not source_texts:
                raise ValueError("No transcription text was returned.")

            detected_language = getattr(transcript, "language", None) or ""
            if not detected_language:
                if selected_language != "Autodetect":
                    detected_language = selected_language
                else:
                    detected_language = "Autodetect"

            # STEP 3: Translate segment-by-segment (batched in one GPT call)
            current_stage = "translation"
            self.set_status("⏳ Translating with GPT-4o...", 85)
            translated = self.translate_segments_with_gpt(source_texts)

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

            self.append_run_log(
                outcome="SUCCESS",
                stage="complete",
                url=url,
                selected_language=selected_language,
                detected_language=detected_language,
            )

            self.set_status("Done!", 100)
            self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))

        except Exception as e:
            error_message = str(e)
            error_type = type(e).__name__
            classified_outcome = classify_error_message(error_message)

            self.log_message(f"\n❌ Error: {error_message}")
            if classified_outcome == "POSSIBLE_SAFETY_BLOCK":
                self.log_message("⚠️ This looks like a possible safety/moderation-related block. Check clip_processing_log.csv for details.")

            self.append_run_log(
                outcome=classified_outcome,
                stage=current_stage,
                url=url,
                selected_language=selected_language,
                detected_language=detected_language,
                error_type=error_type,
                error_message=error_message,
            )

            self.set_status("Error occurred.", 0)
        finally:
            if os.path.exists(audio_filename):
                try:
                    os.remove(audio_filename)
                except Exception:
                    pass

            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))

    # ---------------- Save output ---------------- #
    def save_to_file(self):
        content = self.output_area.get(1.0, tk.END).strip()
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
    root = tk.Tk()
    app = ReelTranslatorApp(root)
    root.mainloop()