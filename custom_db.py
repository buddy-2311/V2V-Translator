import sqlite3

DB_NAME = "dialect_dictionary.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dialect_map (
            id INTEGER PRIMARY KEY,
            dialect_name TEXT,
            standard_word TEXT,
            dialect_word TEXT,
            UNIQUE(dialect_name, standard_word)
        )
    ''')
    conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            src_lang TEXT,
            dest_lang TEXT,
            original_text TEXT,
            translated_text TEXT
        )
    ''')
    conn.commit()

    # Remove Surti completely as requested.
    cursor.execute("DELETE FROM dialect_map WHERE dialect_name = ?", ("Surti",))

    # Kachhi / Kutchi support (Gujarati-base fallback)
    kachhi_data = [
        ("Kachhi", "કેમ છો", "કિયાં આહ્યો"),
        ("Kachhi", "હું", "આઉં"),
        ("Kachhi", "મારું", "મુંજું"),
        ("Kachhi", "તારું", "તુંજું"),
        ("Kachhi", "પાણી", "પાણી"),
        ("Kachhi", "નથી", "ના"),
        ("Kachhi", "શું", "છા"),
        ("Kachhi", "ઘર", "ઘર"),
        ("Kachhi", "મિત્ર", "યાર"),
    ]

    # Kashmiri support (Urdu-base fallback written in Perso-Arabic script)
    kashmiri_data = [
        ("Kashmiri", "آپ کیسے ہیں؟", "تُہۍ چھَو کَسہِ؟"),
        ("Kashmiri", "میں", "بہٕ"),
        ("Kashmiri", "تم", "تُہۍ"),
        ("Kashmiri", "آپ", "تُہۍ"),
        ("Kashmiri", "ہے", "چھُ"),
        ("Kashmiri", "ہیں", "چھِو"),
        ("Kashmiri", "نہیں", "نہ"),
        ("Kashmiri", "کیا", "کیٛاہ"),
        ("Kashmiri", "کہاں", "کُتٮ۪"),
        ("Kashmiri", "پانی", "آب"),
        ("Kashmiri", "گھر", "گر"),
        ("Kashmiri", "دوست", "دوست"),
    ]

    cursor.executemany(
        "INSERT OR REPLACE INTO dialect_map (dialect_name, standard_word, dialect_word) VALUES (?, ?, ?)",
        kachhi_data + kashmiri_data,
    )
    conn.commit()
    conn.close()


def translate_dialect(text, dialect_name):
    """Replaces standard words with dialect words from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT standard_word, dialect_word FROM dialect_map WHERE dialect_name=? ORDER BY LENGTH(standard_word) DESC",
        (dialect_name,),
    )
    mappings = cursor.fetchall()
    conn.close()

    translated_text = text or ""
    for standard, dialect in mappings:
        translated_text = translated_text.replace(standard, dialect)

    return translated_text


if __name__ == "__main__":
    init_db()
    print("Database created/updated for custom regional language mappings.")


def save_history_item(src_lang, dest_lang, original_text, translated_text, timestamp=None):
    from datetime import datetime

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO history_items (timestamp, src_lang, dest_lang, original_text, translated_text)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            src_lang,
            dest_lang,
            original_text,
            translated_text
        )
    )
    conn.commit()
    conn.close()


def get_history_items(limit=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if limit is None:
        cursor.execute(
            """
            SELECT timestamp, src_lang, dest_lang, original_text, translated_text
            FROM history_items
            ORDER BY id DESC
            """
        )
    else:
        cursor.execute(
            """
            SELECT timestamp, src_lang, dest_lang, original_text, translated_text
            FROM history_items
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_history_items(items_to_delete):
    """Delete matching history rows from SQLite history_items."""
    if not items_to_delete:
        return 0
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    deleted = 0
    for ts, src, dst, orig, trans in items_to_delete:
        cursor.execute(
            """
            DELETE FROM history_items
            WHERE timestamp=? AND src_lang=? AND dest_lang=? AND original_text=? AND translated_text=?
            """,
            (str(ts or ""), str(src or ""), str(dst or ""), str(orig or ""), str(trans or ""))
        )
        deleted += cursor.rowcount
    conn.commit()
    conn.close()
    return deleted
