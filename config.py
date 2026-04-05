HISTORY_FILE = "history.csv"
SAMPLE_RATE = 16000
BLOCK_SIZE = 800
THEME_NAME = "superhero"

# ✅ New: force a specific mic device (None = auto)
MIC_DEVICE_INDEX = None  # set to integer like 0,1,2... from Settings dropdown

# ✅ New: tweak recognition in noisy rooms
NOISY_ROOM_MODE = True

LANGUAGES = {
    "Auto-Detect": {"sr": "en-IN", "tts": "en", "tr": "auto", "is_auto": True},  # STT uses broad lang; translation always uses src="auto"
    "English":   {"sr": "en-IN", "tts": "en", "tr": "en"},
    "Hindi":     {"sr": "hi-IN", "tts": "hi", "tr": "hi"},
    "Gujarati":  {"sr": "gu-IN", "tts": "gu", "tr": "gu"},
    "Kachhi":    {"sr": "gu-IN", "tts": "gu", "tr": "kachhi", "is_custom": True, "base_lang": "gu"},
    "Punjabi":   {"sr": "pa-IN", "tts": "pa", "tr": "pa"},
    "Marathi":   {"sr": "mr-IN", "tts": "mr", "tr": "mr"},
    "Tamil":     {"sr": "ta-IN", "tts": "ta", "tr": "ta"},
    "Telugu":    {"sr": "te-IN", "tts": "te", "tr": "te"},
    "Bengali":   {"sr": "bn-IN", "tts": "bn", "tr": "bn"},
    "Kannada":   {"sr": "kn-IN", "tts": "kn", "tr": "kn"},
    "Malayalam": {"sr": "ml-IN", "tts": "ml", "tr": "ml"},
    "Odia":      {"sr": "or-IN", "tts": "or", "tr": "or"},
    "Assamese":  {"sr": "bn-IN", "tts": "bn", "tr": "as"},
    "Urdu":      {"sr": "ur-PK", "tts": "ur", "tr": "ur"},
    "Arabic":    {"sr": "ar-SA", "tts": "ar", "tr": "ar"},
    "Spanish":   {"sr": "es-ES", "tts": "es", "tr": "es"},
    "French":    {"sr": "fr-FR", "tts": "fr", "tr": "fr"},
    "German":    {"sr": "de-DE", "tts": "de", "tr": "de"},
    "Japanese":  {"sr": "ja-JP", "tts": "ja", "tr": "ja"},
    "Chinese":   {"sr": "zh-CN", "tts": "zh-CN", "tr": "zh-CN"},
    "Korean":    {"sr": "ko-KR", "tts": "ko", "tr": "ko"},
    "Russian":   {"sr": "ru-RU", "tts": "ru", "tr": "ru"},
    "Italian":   {"sr": "it-IT", "tts": "it", "tr": "it"},
    "Kashmiri":  {"sr": "ur-PK", "tts": "ur", "tr": "kashmiri", "is_custom": True, "base_lang": "ur"},
}
