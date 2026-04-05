# audio_engine.py
import speech_recognition as sr
from deep_translator import GoogleTranslator, MyMemoryTranslator
from gtts import gTTS
import uuid
import audioop
import os
from typing import cast

 
def record_audio(duration: int = 5):
    """
    Records audio and returns (AudioData, RMS loudness)
    """
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio_data: sr.AudioData = recognizer.listen(
            source, phrase_time_limit=duration
        ) # type: ignore

    try:
        raw_data = audio_data.get_raw_data()
        rms = audioop.rms(raw_data, 2)
    except Exception:
        rms = 0

    return audio_data, rms



def speech_to_text(audio: sr.AudioData, lang_code="en-IN") -> str:
    recognizer = sr.Recognizer()
    try:
        return recognizer.recognize_google(audio, language=lang_code)  # type: ignore
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return "API Error"


def transcribe_file(filepath, lang_code="en-IN"):
    recognizer = sr.Recognizer()
    with sr.AudioFile(filepath) as source:
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio, language=lang_code)  # type: ignore
        return text, 1000
    except sr.UnknownValueError:
        return "", 0
    except Exception:
        return "", 0


# audio_engine.py
from deep_translator import GoogleTranslator
import custom_db  # Import your new database file

# Ensure database is initialized
custom_db.init_db()

def translate_text(text: str, src="auto", dest="hi", dest_name="Hindi") -> str:
    text = (text or "").strip()
    if not text:
        return ""
    try:
        # Check if the destination is one of your CUSTOM dialects
        if dest in ["surti", "kutchi"]:
            # Step 1: Translate to the base language first (e.g., standard Gujarati)
            # You can determine base language from your config. 
            base_lang = "gu" # hardcoded for this example, but fetch from config ideally
            standard_translation = GoogleTranslator(source=src, target=base_lang).translate(text)
            
            # Step 2: Pass through YOUR database
            dialect_translation = custom_db.translate_dialect(standard_translation, dest.capitalize())
            return dialect_translation
            
        else:
            # Standard Google translation for regular languages
            return GoogleTranslator(source=src, target=dest).translate(text)
            
    except Exception as e:
        return f"Translation failed: {e}"


def make_tts_audio(text, lang):
    if not text:
        return None

    try:
        tts = gTTS(text=text, lang=lang)
        filename = f"temp_{uuid.uuid4().hex}.mp3"
        tts.save(filename)
        return filename
    except Exception as e:
        print("TTS Error:", e)
        return None


def wait_for_wake_word(wake_word="nova", lang_code="en-IN"):
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)
            text = recognizer.recognize_google(audio, language=lang_code).lower()  # type: ignore

            if wake_word.lower() in text:
                return True
        except Exception:
            return False

    return False


