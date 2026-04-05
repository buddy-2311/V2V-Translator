# engine.py
from __future__ import annotations

import os
import uuid
import audioop
import tempfile
import threading
import time
import subprocess
import shutil
from typing import Tuple, Optional
 
import speech_recognition as sr
import numpy as np
import sounddevice as sd
from deep_translator import GoogleTranslator, MyMemoryTranslator
import PyPDF2
from gtts import gTTS
from playsound import playsound

try:
    import pygame
except Exception:
    pygame = None
import custom_db

try:
    from docx import Document
except Exception:
    Document = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from PIL import Image
except Exception:
    Image = None

WhisperModel = None  # FORCE WHISPER OFF
custom_db.init_db()


class Engine:
    """
    HIGHER recognition quality version:
      - Uses SpeechRecognition Microphone capture (PyAudio) -> cleaner laptop audio
      - Whisper STT with forced language + fallback
      - Keeps your main.py signatures:
          record_audio(sec) -> AudioData
          speech_to_text(audio, lang) -> (text, confidence)
    """

    

    def __init__(self):
        self.recognizer = sr.Recognizer()

        # ✅ Tune SR for better capture
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.9          # allow small pauses
        self.recognizer.phrase_threshold = 0.2
        self.recognizer.non_speaking_duration = 0.6

        # Whisper
        self._whisper = None
        self._model_name = "base"   # best accuracy for Indic languages
        self._whisper_lock = threading.Lock()

        # ✅ ADD THIS BLOCK
        try:
            with sr.Microphone() as source:
                pass
            self.mic_available = True
        except Exception:
            self.mic_available = False

        self.stop_requested = False
        self._recording_active = False
        self._tts_active = False
        self._playback_file = None
        self._audio_lock = threading.Lock()

        if pygame is not None:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
            except Exception:
                pass


    def reset_stop_flag(self):
        self.stop_requested = False

    def stop_all(self):
        """
        Universal stop:
        - microphone recording
        - TTS playback
        - long file/translation loops
        """
        self.stop_requested = True

        try:
            sd.stop()
        except Exception:
            pass

        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
        except Exception:
            pass

        self._recording_active = False
        self._tts_active = False

    def handle_nova_command(self, text):
        """
        Returns: command_name or None
        Supported:
        - hey nova stop
        - hey nova clear the screen
        - hey nova repeat
        - hey nova start listening
        """
        t = (text or "").strip().lower()
        if not t:
            return None

        t = t.replace(",", " ").replace(".", " ").strip()

        commands = {
            "hey nova stop": "stop",
            "stop nova": "stop",
            "hey nova clear the screen": "clear",
            "nova clear the screen": "clear",
            "hey nova repeat": "repeat",
            "nova repeat": "repeat",
            "hey nova start listening": "start_listening",
            "nova start listening": "start_listening",
        }

        for phrase, cmd in commands.items():
            if phrase in t:
                return cmd

        return None

    # =========================
    # TTS
    # =========================
    def speak(self, text: str, lang: str = "en") -> None:
        if not text:
            return

        self._tts_active = True
        filename = f"temp_{uuid.uuid4().hex}.mp3"
        self._playback_file = filename

        try:
            gTTS(text=text, lang=lang).save(filename)

            if self.stop_requested:
                return

            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy():
                    if self.stop_requested:
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.08)
            else:
                playsound(filename)

        finally:
            self._tts_active = False
            self._playback_file = None
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass

    def make_tts_audio(self, text, lang="en", speed=150):
        self.speak(str(text), lang=lang)
        return None

    # =========================
    # RECORD (better mic capture)
    # =========================
    def record_audio(self, duration: int = 5) -> sr.AudioData:
        with sr.Microphone() as source:
            # 🛑 FIX 1: We removed `adjust_for_ambient_noise` here! 
            # It was causing a 1-second delay that missed the first word of your sentence.
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = 300  # Set static threshold to catch speech instantly
            
            print("[🎙️ Record] Listening for your command...")
            try:
                audio: sr.AudioData = self.recognizer.listen(
                    source,
                    timeout=5, # Don't wait forever
                    phrase_time_limit=max(8, int(duration) + 5)
                ) # type: ignore
                print("[🎙️ Record] Audio captured!")
                return audio
            except Exception as e:
                print(f"[⚠️ Record Error] {e}")
                # Return empty audio data if it times out, avoiding crashes
                return sr.AudioData(b'', 16000, 2)
    

    def calculate_loudness(self, audio: sr.AudioData) -> float:
        try:
            return float(audioop.rms(audio.get_raw_data(), 2))
        except Exception:
            return 0.0

    # =========================
    # Whisper
    # =========================
    def _ensure_whisper(self):
        if WhisperModel is None:
            raise RuntimeError("Install faster-whisper.")

        with self._whisper_lock:
            if self._whisper is None:
                self._whisper = WhisperModel(
                    self._model_name,
                    device="cpu",
                    compute_type="int8"
                )

        return self._whisper


   # =========================
    # SPEECH TO TEXT (Bulletproof + Advanced Whisper)
    # =========================
    # =========================
    # SPEECH TO TEXT (Bulletproof + Advanced Whisper)
    # =========================
    def speech_to_text(self, audio: sr.AudioData, lang: str = "en-IN") -> Tuple[str, float]:
        # Extract base language (e.g., 'hi-IN' -> 'hi')
        base = (lang or "en").split("-")[0].lower()

        # 1. Google Fallback if Whisper is not installed
        if WhisperModel is None:
            try:
                print(f"[🧠 STT] Sending to Google ({lang})...")
                text = self.recognizer.recognize_google(audio, language=lang) # type: ignore
                print(f"[✅ STT Success] Google heard: '{text}'")
                return text, 0.9
            except Exception as e:
                print(f"[⚠️ STT Error] Google failed: {e}")
                return "", 0.0

        # 2. Ensure Whisper can load
        try:
            self._ensure_whisper()
        except Exception as e:
            print(f"[⚠️ STT Error] Whisper failed to load: {e}")
            return "", 0.0

        # --- YOUR ADVANCED WHISPER CODE STARTS HERE ---
        
        # Convert audio to Whisper's required format (16kHz)
        import tempfile
        wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            print(f"[🧠 STT] Sending to Whisper ({base})...")
            # Lock ensures we don't accidentally run two translations at the exact same millisecond
            with self._whisper_lock: 
                model = self._ensure_whisper()
                
                # Pass 1: Forced language
                segments, _ = model.transcribe(
                    tmp_path,
                    task="transcribe",
                    language=base,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    temperature=0.0,
                    beam_size=4,
                    best_of=4,
                    no_speech_threshold=0.35,
                    log_prob_threshold=-1.0,
                    compression_ratio_threshold=2.4,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()

                # Pass 2: Auto detect fallback
                if not text:
                    segments2, _ = model.transcribe(
                        tmp_path,
                        task="transcribe",
                        language=None,
                        vad_filter=False,
                        condition_on_previous_text=False,
                        temperature=0.0,
                        beam_size=4,
                        best_of=4,
                    )
                    text = " ".join(seg.text.strip() for seg in segments2).strip()

            print(f"[✅ STT Success] Whisper heard: '{text}'")
            return (text, 0.93) if text else ("", 0.0)

        except Exception as e:
            # Last fallback to Google just in case Whisper crashes mid-sentence
            print(f"[⚠️ STT Error] Whisper crashed, falling back to Google... ({e})")
            try:
                fallback_text = self.recognizer.recognize_google(audio, language=lang) # type: ignore
                print(f"[✅ STT Success] Google Fallback heard: '{fallback_text}'")
                return fallback_text, 0.9
            except Exception:
                 return f"Whisper failed: {e}", 0.0
        finally:
            # Always delete the temporary file!
            try:
                import os
                os.remove(tmp_path)
            except:
                pass

    # =========================
    # Punctuation
    # =========================
    def apply_smart_punctuation(self, text: str, loudness_score: float) -> str:
        if not text:
            return ""
        t = text.strip()
        if not t:
            return ""
        t = t[:1].upper() + t[1:]
        if t[-1] in ".?!":
            return t
        return t + ("!" if loudness_score > 3000 else ".")

    # =========================
    # Translation
    # =========================
    def _translate_single_chunk(self, text: str, src="auto", dest="hi") -> str:
        # Custom Kachhi pipeline: translate to Gujarati first, then apply local mappings.
        if dest == "kachhi":
            base_text = GoogleTranslator(source=src, target="gu").translate(text)
            return custom_db.translate_dialect(base_text, "Kachhi")

        # Custom Kashmiri pipeline:
        # 1) try native Google target if available
        # 2) fallback to Urdu and then apply Kashmiri rule mappings
        if dest == "kashmiri":
            try:
                return GoogleTranslator(source=src, target="ks").translate(text)
            except Exception:
                base_text = GoogleTranslator(source=src, target="ur").translate(text)
                return custom_db.translate_dialect(base_text, "Kashmiri")

        if dest == "xyz":
            return MyMemoryTranslator(source=src, target=dest).translate(text)

        return GoogleTranslator(source=src, target=dest).translate(text)

    def _split_text_for_translation(self, text: str, max_chars: int = 3000):
        text = (text or "").strip()
        if len(text) <= max_chars:
            return [text]

        blocks = []
        current = ""
        for para in text.split("\n"):
            para = para.strip()
            if not para:
                continue
            candidate = f"{current}\n{para}".strip() if current else para
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                blocks.append(current)
                current = ""
            while len(para) > max_chars:
                split_at = para.rfind(" ", 0, max_chars)
                if split_at <= 0:
                    split_at = max_chars
                blocks.append(para[:split_at].strip())
                para = para[split_at:].strip()
            if para:
                current = para
        if current:
            blocks.append(current)
        return blocks or [text]

    def translate_text(self, text: str, src="auto", dest="hi") -> str:
        text = (text or "").strip()
        if not text:
            return ""
        try:
            chunks = self._split_text_for_translation(text)
            translated_parts = []
            for chunk in chunks:
                if self.stop_requested:
                    return ""
                if not chunk.strip():
                    continue
                translated_parts.append(self._translate_single_chunk(chunk, src=src, dest=dest))
            return "\n\n".join(part for part in translated_parts if part is not None)
        except Exception as e:
            return f"Translation failed: {e}"

    # =========================
    # Files
    # =========================
    def _convert_media_to_wav(self, file_path: str) -> str:
        """Convert almost any audio/video file to mono 16k wav using ffmpeg."""
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise RuntimeError("FFmpeg is required for audio/video upload support.")

        out_path = os.path.join(tempfile.gettempdir(), f"nova_{uuid.uuid4().hex}.wav")
        cmd = [
            ffmpeg_path, "-y", "-i", file_path,
            "-ac", "1", "-ar", "16000", "-vn", out_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not os.path.exists(out_path):
            raise RuntimeError("Could not convert uploaded media file.")
        return out_path

    def _is_audio_or_video(self, filepath: str) -> bool:
        ext = os.path.splitext(filepath)[1].lower()
        return ext in {
            ".wav", ".mp3", ".m4a", ".ogg", ".opus", ".aac", ".flac", ".wma",
            ".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg"
        }

    def transcribe_file(self, file_path: str, lang="en-IN"):
        cleanup_path = None
        try:
            actual_path = file_path
            if os.path.splitext(file_path)[1].lower() != ".wav":
                actual_path = self._convert_media_to_wav(file_path)
                cleanup_path = actual_path
            with sr.AudioFile(actual_path) as source:
                audio = self.recognizer.record(source)
            return self.speech_to_text(audio, lang)
        finally:
            if cleanup_path and os.path.exists(cleanup_path):
                try:
                    os.remove(cleanup_path)
                except Exception:
                    pass

    def read_txt_file(self, filepath: str) -> str:
        encodings = ["utf-8", "utf-8-sig", "utf-16", "cp1252", "latin-1"]
        last_error = None
        for enc in encodings:
            try:
                with open(filepath, "r", encoding=enc, errors="strict") as f:
                    return f.read()
            except Exception as e:
                last_error = e
                continue
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
        if data:
            return data
        raise RuntimeError(f"Could not read text file: {last_error}")

    def read_pdf_file(self, filepath: str) -> str:
        text = ""
        with open(filepath, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                if self.stop_requested:
                    break
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text.strip()

    def extract_text_from_file(self, filepath: str) -> str:
        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".txt":
            return self.read_txt_file(filepath)

        if ext == ".pdf":
            return self.read_pdf_file(filepath)

        if ext == ".docx":
            if Document is None:
                return "DOCX support requires python-docx."
            doc = Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs).strip()

        if ext in [".jpg", ".jpeg", ".png"]:
            if pytesseract is None or Image is None:
                return "Image OCR support requires pytesseract and pillow."
            return pytesseract.image_to_string(Image.open(filepath)).strip()

        return "Unsupported file type."

    # =========================
    # Wake word
    # =========================
    # =========================
    # Wake word
    # =========================
    def wait_for_wake_word_blocking(self, wake_word="nova", lang="en-IN") -> bool:
        wake_word = (wake_word or "nova").lower()
        # Common misspellings of Nova
        variants = ["nova", "noah", "noha", "noba", "nowa", "novah", "inova"]
    
        with sr.Microphone() as source:
            # Force it to stop waiting endlessly for silence
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = 400  # Raise to 600 or 800 if you are in a loud room
            
            # Calibrate ambient noise
            self.recognizer.adjust_for_ambient_noise(source, duration=0.6) # type: ignore
            
            print("[⏳ Wake Word] Listening for 'Nova'...")
            
            try:
                # Wait patiently until you speak (timeout=None), but only record for up to 4 seconds
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=4)
                
                # Send to Google to instantly check what you said
                text = self.recognizer.recognize_google(audio, language=lang).lower() # type: ignore
                print(f"[🗣️ Wake Word] I heard: '{text}'")
                
                # Check if it heard Nova or any of the variations
                if wake_word in text: 
                    return True
                for variant in variants:
                    if variant in text: 
                        return True
                        
                return False
                
            except sr.UnknownValueError:
                # It heard a sound but no valid words
                return False
            except Exception as e:
                # Print real errors to the terminal so we can debug
                print(f"[⚠️ Wake Word Error] {e}")
                return False