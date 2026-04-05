import os
import csv
import re
from datetime import datetime
from textblob import TextBlob  # Required for Emotion Detection

HISTORY_FILE = "history.csv"

def apply_smart_punctuation(text, loudness_score=0):
    """
    Analyzes text and loudness to insert punctuation.
    """
    if not text: 
        return ""
    
    # Clean whitespace
    text = text.strip()
    
    # 1. Capitalize first letter
    text = text[0].upper() + text[1:]
    
    # 2. explicit punctuation replacement
    replacements = {
        " comma": ",", " dot": ".", " full stop": ".", " period": ".",
        " question mark": "?", " exclamation mark": "!", 
        " colon": ":", " semi colon": ";"
    }
    
    lower_text = text.lower()
    for word, mark in replacements.items():
        if word in lower_text:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            text = pattern.sub(mark, text)

    # 3. Auto-detect sentence Ending
    q_starters = ("Who", "What", "Where", "When", "Why", "How", "Is", "Are", "Do", "Does", "Did", "Can", "Could", "Would", "Should", "Will")
    
    if text[-1] not in "?!.:":
        if text.startswith(q_starters):
            text += "?"
        elif loudness_score > 2000: 
            text += "!"
        else:
            text += "."
            
    return text

def get_sentiment(text):
    """
    Analyzes text sentiment.
    Returns: (Emoji, ColorTheme, EmotionName)
    """
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity # -1 to 1

        if polarity > 0.3:
            return "😃", "success", "Happy"
        elif polarity < -0.3:
            return "😠", "danger", "Angry/Sad"
        else:
            return "😐", "info", "Neutral"
    except:
        return "", "info", "Neutral"

def log_history(src_lang, dest_lang, original, translated):
    file_exists = os.path.isfile(HISTORY_FILE)
    try:
        with open(HISTORY_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "From", "To", "Original", "Translated"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), src_lang, dest_lang, original, translated])
    except Exception as e:
        print(f"Error saving history: {e}")

def read_last_history(limit=50):
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            data = list(reader)
            if len(data) < 2: return []
            rows = data[1:]
            return rows[-limit:][::-1]
    except: return []

def safe_delete(filename):
    if filename and os.path.exists(filename):
        try: os.remove(filename)
        except: pass

def analyze_punctuation(text):
    """
    Detect punctuation pattern and return a short tone explanation.
    Supports: ?, !, ., ,, !!, ?!, ...
    """
    text = (text or "").strip()
    if not text:
        return "Tone: no punctuation detected"

    if text.endswith("?!"):
        return "Tone: surprise + confusion"
    if text.endswith("!!"):
        return "Tone: excited / strong emotion"
    if text.endswith("..."):
        return "Tone: hesitation / trailing thought"
    if text.endswith("?"):
        return "Tone: question"
    if text.endswith("!"):
        return "Tone: emphasis / excitement"
    if text.endswith("."):
        return "Tone: statement"
    if "," in text:
        return "Tone: pause / continuation"

    return "Tone: neutral"


def read_all_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            data = list(reader)
            if len(data) < 2:
                return []
            return data[1:][::-1]
    except Exception:
        return []


def rewrite_history(rows):
    try:
        with open(HISTORY_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "From", "To", "Original", "Translated"])
            for row in rows:
                writer.writerow(list(row))
        return True
    except Exception as e:
        print(f"Error rewriting history: {e}")
        return False


def delete_history_items(items_to_delete):
    if not os.path.exists(HISTORY_FILE):
        return 0
    target = {
        (str(ts or ""), str(src or ""), str(dst or ""), str(orig or ""), str(trans or ""))
        for ts, src, dst, orig, trans in items_to_delete
    }
    rows = read_all_history()[::-1]  # back to file order oldest -> newest
    kept = [row for row in rows if tuple(str(v or "") for v in row) not in target]
    if rewrite_history(kept):
        return len(rows) - len(kept)
    return 0
