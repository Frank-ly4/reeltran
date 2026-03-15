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
if not os.path.exists(SAVED_FOLDER): os.makedirs(SAVED_FOLDER)

# --- 3. AUTO-DEPENDENCY INSTALLER ---
def ensure_dependencies():
    required_libs = ["yt-dlp", "openai-whisper", "openai"]
    for lib in required_libs:
        try:
            if lib == "openai-whisper": import whisper
            else: __import__(lib)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", lib], capture_output=True)

ensure_dependencies()

# --- 4. MAIN APPLICATION ---
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import threading
import yt_dlp
import whisper
from openai import OpenAI

# ==========================================
# PASTE YOUR OPENAI API KEY HERE
OPENAI_API_KEY = "YOURKEYHERE" 
# ==========================================

class ReelTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Thai Reel Translator FAST & ELITE (Turbo + GPT-4o)")
        self.root.geometry("850x800")
        self.root.resizable(False, False)
        
        # Initialize OpenAI Client safely
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY != "your-key-here" else None
        self.whisper_model = None
        
        self._build_ui()

    def _build_ui(self):
        # URL Input
        input_frame = tk.Frame(self.root, pady=10)
        input_frame.pack(fill=tk.X, padx=20)
        tk.Label(input_frame, text="Reel URL:", font=("Arial", 11)).pack(side=tk.LEFT)
        self.url_entry = tk.Entry(input_frame, font=("Arial", 11), width=50)
        self.url_entry.pack(side=tk.LEFT, padx=10)
        self.process_btn = tk.Button(input_frame, text="Process Reel", font=("Arial", 10, "bold"), 
                                     bg="#007bff", fg="white", command=self.start_processing)
        self.process_btn.pack(side=tk.LEFT)

        # Status & Progress
        status_frame = tk.Frame(self.root, pady=5)
        status_frame.pack(fill=tk.X, padx=20)
        self.status_label = tk.Label(status_frame, text="Ready", font=("Arial", 10, "italic"), fg="#555")
        self.status_label.pack(side=tk.LEFT)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=20, pady=(0, 10))

        # Output Area
        self.output_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, font=("Consolas", 11), height=26)
        self.output_area.pack(fill=tk.BOTH, padx=20, pady=5)

        # Save Button
        self.save_btn = tk.Button(self.root, text="Save to SavedText Folder", font=("Arial", 11), 
                                  command=self.save_to_file, state=tk.DISABLED)
        self.save_btn.pack(pady=10)

    def set_status(self, text, progress=None):
        self.root.after(0, lambda: self.status_label.config(text=text))
        if progress is not None: self.root.after(0, lambda: self.progress_var.set(progress))

    def log_message(self, message):
        self.root.after(0, lambda: self.output_area.insert(tk.END, message + "\n"))
        self.root.after(0, lambda: self.output_area.see(tk.END))

    def start_processing(self):
        if not self.client:
            messagebox.showerror("API Key Missing", "Please paste your OpenAI API Key into the OPENAI_API_KEY variable in the code.")
            return
            
        url = self.url_entry.get().strip()
        if not url: return
        
        self.process_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.output_area.delete(1.0, tk.END)
        threading.Thread(target=self.process_video, args=(url,), daemon=True).start()

    def translate_batch_with_gpt(self, thai_segments):
        """Sends all segments to GPT-4o at once for maximum speed and context."""
        if not thai_segments:
            return {}

        # 1. Prepare the numbered list
        prompt_text = ""
        for i, text in enumerate(thai_segments):
            prompt_text += f"{i+1}. {text}\n"

        system_instruction = (
            "You are a professional Thai-to-English translator. "
            "You will receive a numbered list of transcript segments. "
            "Translate each segment into English, maintaining the flow, slang, and emotional nuance. "
            "CRITICAL: You must return ONLY the translated numbered list. Do not include any intro, outro, or conversational text. "
            "Keep the exact same numbering format."
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.3 # Low temperature keeps it focused and less likely to hallucinate
            )
            
            output_text = response.choices[0].message.content.strip()
            
            # 2. Parse the returned numbered list back into a dictionary
            translated_dict = {}
            for line in output_text.split('\n'):
                # Look for lines starting with numbers (e.g., "1. Translation text")
                match = re.match(r'^(\d+)\.\s*(.*)', line.strip())
                if match:
                    index = int(match.group(1)) - 1 # Convert back to 0-based index
                    translated_dict[index] = match.group(2)
            
            return translated_dict

        except Exception as e:
            self.log_message(f"❌ Batch Translation Error: {str(e)}")
            return {}

    def process_video(self, url):
        timestamp = datetime.now().strftime("%H%M%S")
        audio_filename = f"temp_audio_{timestamp}.mp3"
        
        try:
            # STEP 1: DOWNLOAD
            self.set_status("⏳ Downloading audio...", 15)
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_filename.replace(".mp3", ""),
                'ffmpeg_location': current_dir,
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                'quiet': True, 'noprogress': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # STEP 2: LOAD FASTER MODEL
            self.set_status("⏳ Loading Whisper Turbo Model...", 35)
            if self.whisper_model is None:
                self.whisper_model = whisper.load_model("turbo") # Speed optimized version of large-v3

            # STEP 3: TRANSCRIBE LOCALLY
            self.set_status("⏳ Transcribing Thai (Local CPU)...", 60)
            thai_hint = "นี่คือคลิปวิดีโอจากอินสตาแกรม พูดถึงเรื่องหมาและประเด็นดราม่าที่เกิดขึ้น"
            result = self.whisper_model.transcribe(
                audio_filename, 
                language="th", 
                initial_prompt=thai_hint,
                fp16=False,
                condition_on_previous_text=True
            )

            # Extract valid text segments
            valid_segments = []
            thai_texts_for_gpt = []
            for seg in result['segments']:
                txt = seg['text'].strip()
                if len(txt) >= 2: # Skip weird background noise blips
                    valid_segments.append(seg)
                    thai_texts_for_gpt.append(txt)

            # STEP 4: BATCH TRANSLATE VIA API
            self.set_status("⏳ GPT-4o is translating the entire transcript...", 85)
            translated_dict = self.translate_batch_with_gpt(thai_texts_for_gpt)

            # STEP 5: DISPLAY OUTPUT
            self.log_message(f"FAST BATCH TRANSCRIPTION ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n" + "="*50)
            
            for i, seg in enumerate(valid_segments):
                time_info = f"[{seg['start']:.1f}s - {seg['end']:.1f}s]"
                th_text = thai_texts_for_gpt[i]
                en_text = translated_dict.get(i, "[Translation failed for this line]")
                
                self.log_message(f"{time_info}\nTH: {th_text}\nEN: {en_text}\n")

            self.log_message("="*50 + "\n✅ Finished!")
            self.set_status("Done!", 100)
            self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))

        except Exception as e:
            self.log_message(f"\n❌ Error: {str(e)}")
            self.set_status("Error occurred.", 0)
        finally:
            if os.path.exists(audio_filename):
                try: os.remove(audio_filename)
                except: pass
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))

    def save_to_file(self):
        content = self.output_area.get(1.0, tk.END).strip()
        if not content: return
        fname = f"Fast_Reel_{datetime.now().strftime('%Y-%m-%d_%H%M')}.txt"
        path = filedialog.asksaveasfilename(initialdir=SAVED_FOLDER, initialfile=fname, defaultextension=".txt")
        if path:
            with open(path, 'w', encoding='utf-8') as f: f.write(content)
            messagebox.showinfo("Success", "File saved!")

if __name__ == "__main__":
    root = tk.Tk()
    app = ReelTranslatorApp(root)
    root.mainloop()