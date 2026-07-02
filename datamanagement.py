import sqlite3
import json


def create_database():
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            gmail TEXT
        )
    ''')
    # Backfill older databases created before gmail was added.
    cursor.execute("PRAGMA table_info(users)")
    columns = {col[1] for col in cursor.fetchall()}
    if "gmail" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN gmail TEXT")
    conn.commit()
    conn.close()

def create_videos_database():
    conn = sqlite3.connect('videos.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            author TEXT,
            title TEXT NOT NULL,
            platform TEXT NOT NULL,
            platforms_posted TEXT,
            date_published TEXT,
            description TEXT,
            link TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            views INTEGER NOT NULL DEFAULT 0,
            likes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Backfill older videos databases that do not have the newer publishing fields.
    cursor.execute("PRAGMA table_info(videos)")
    columns = {col[1] for col in cursor.fetchall()}
    if "author" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN author TEXT")
    if "platforms_posted" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN platforms_posted TEXT")
    if "date_published" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN date_published TEXT")
    if "description" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN description TEXT")
    if "link" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN link TEXT")

    conn.commit()
    conn.close()


def publish_video(author, title, date_published, description, platforms_posted, link,
                  user_id=None, status="published", views=0, likes=0):
    if isinstance(platforms_posted, (list, tuple)):
        platforms_list = [str(platform).strip() for platform in platforms_posted if str(platform).strip()]
    else:
        platforms_list = [str(platforms_posted).strip()] if str(platforms_posted).strip() else []

    primary_platform = platforms_list[0] if platforms_list else "unknown"
    platforms_json = json.dumps(platforms_list)

    conn = sqlite3.connect('videos.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO videos (
            user_id,
            author,
            title,
            platform,
            platforms_posted,
            date_published,
            description,
            link,
            status,
            views,
            likes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        author,
        title,
        primary_platform,
        platforms_json,
        date_published,
        description,
        link,
        status,
        views,
        likes
    ))
    video_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return video_id


def get_videos_by_username(username):
    conn = sqlite3.connect('videos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            id,
            user_id,
            author,
            title,
            platform,
            platforms_posted,
            date_published,
            description,
            link,
            status,
            views,
            likes,
            created_at
        FROM videos
        WHERE author = ?
        ORDER BY COALESCE(date_published, created_at) DESC, id DESC
    ''', (username,))
    rows = cursor.fetchall()
    conn.close()

    videos = []
    for row in rows:
        platforms = []
        raw_platforms = row["platforms_posted"]
        if raw_platforms:
            try:
                decoded = json.loads(raw_platforms)
                if isinstance(decoded, list):
                    platforms = [str(platform).strip() for platform in decoded if str(platform).strip()]
            except json.JSONDecodeError:
                platforms = [part.strip() for part in raw_platforms.split(",") if part.strip()]
        if not platforms and row["platform"]:
            platforms = [row["platform"]]

        videos.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "author": row["author"],
            "title": row["title"],
            "platform": row["platform"],
            "platforms_posted": platforms,
            "date_published": row["date_published"],
            "description": row["description"],
            "link": row["link"],
            "status": row["status"] or "draft",
            "views": row["views"] or 0,
            "likes": row["likes"] or 0,
            "created_at": row["created_at"]
        })
    return videos


def login(username, password):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM users WHERE username = ? AND password = ?
    ''', (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return user
    else:
        return False


def signup(username, password, gmail=None):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (username, password, gmail) VALUES (?, ?, ?)
    ''', (username, password, gmail))
    conn.commit()
    conn.close()


def check_username_exists(username):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM users WHERE username = ?
    ''', (username,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return True
    else:
        return False


create_database()
create_videos_database()
