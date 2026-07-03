import os
import html
import json

from flask import Flask, render_template, request, jsonify, redirect, session
from google_auth_oauthlib.flow import Flow
from datetime import datetime, timedelta
from datamanagement import (
    login as db_login,
    signup as db_signup,
    check_username_exists,
    get_videos_by_username,
    get_auth_tokens,
    update_auth_tokens,
)
from publishing import publish_to_youtube

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-change-me")

YOUTUBE_CLIENT_SECRETS_FILE = os.path.join(
    os.path.dirname(__file__),
    "oath",
    "creds",
    "client_secret_778206428456-7fb0qkmibu7applvmih8hs521toaem5h.apps.googleusercontent.com.json",
)
YOUTUBE_OAUTH_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_youtube_oauth_client_config():
    with open(YOUTUBE_CLIENT_SECRETS_FILE, "r", encoding="utf-8") as f:
        client_config = json.load(f)
    web_config = client_config.get("web") or {}
    redirect_uris = web_config.get("redirect_uris") or []
    return {
        "client_id": web_config.get("client_id", ""),
        "redirect_uri": redirect_uris[0] if redirect_uris else "",
    }


YOUTUBE_OAUTH_CLIENT_CONFIG = _load_youtube_oauth_client_config()
YOUTUBE_REDIRECT_URI = YOUTUBE_OAUTH_CLIENT_CONFIG["redirect_uri"]


def _parse_date(value):
    if not value:
        return None
    date_portion = str(value).strip()[:10]
    try:
        return datetime.strptime(date_portion, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_home_data(username, videos, youtube_connected=False):
    videos_count = len(videos)
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=6)

    posts_this_week = 0
    for video in videos:
        published_date = _parse_date(video.get("date_published"))
        if published_date and week_start <= published_date <= today:
            posts_this_week += 1

    newest_video = videos[0] if videos else None
    newest_views = newest_video["views"] if newest_video else 0
    newest_likes = newest_video["likes"] if newest_video else 0
    newest_engagement = (newest_likes / newest_views * 100) if newest_views else 0

    platform_totals = {
        "youtube": {"name": "YouTube", "videos": 0, "views": 0, "likes": 0},
        "tiktok": {"name": "TikTok", "videos": 0, "views": 0, "likes": 0},
    }

    for video in videos:
        platforms = video.get("platforms_posted") or []
        if not platforms and video.get("platform"):
            platforms = [video["platform"]]
        unique_platforms = {str(platform).strip().lower() for platform in platforms if str(platform).strip()}
        for platform_key in unique_platforms:
            if platform_key in platform_totals:
                platform_totals[platform_key]["videos"] += 1
                platform_totals[platform_key]["views"] += int(video.get("views", 0) or 0)
                platform_totals[platform_key]["likes"] += int(video.get("likes", 0) or 0)

    platform_analytics = []
    for platform_key in ("youtube", "tiktok"):
        stats = platform_totals[platform_key]
        views = stats["views"]
        likes = stats["likes"]
        engagement = (likes / views * 100) if views else 0
        growth_score = min(100, int(engagement * 8)) if views else 0
        platform_analytics.append({
            "name": stats["name"],
            "videos_published": stats["videos"],
            "total_views": views,
            "total_likes": likes,
            "engagement_rate": round(engagement, 2),
            "growth_score": growth_score,
        })

    return {
        "username": username,
        "youtube_connected": youtube_connected,
        "recent_posts": videos[:20],
        "metrics": {
            "posts_this_week": posts_this_week,
            "posts_all_time": videos_count,
        },
        "newest_video": {
            "title": newest_video["title"] if newest_video else "No videos yet",
            "platforms_text": ", ".join(newest_video.get("platforms_posted", [])) if newest_video else "YouTube, TikTok",
            "views": newest_views,
            "likes": newest_likes,
            "engagement_rate": round(newest_engagement, 2),
            "published_date": newest_video.get("date_published") if newest_video else None,
        },
        "platform_analytics": platform_analytics,
    }


def _credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def _home_post_redirect_response(username):
    safe_username = html.escape(username or "", quote=True)
    html = f"""
<!DOCTYPE html>
<html lang="en">
<body>
  <form id="homeRedirectForm" method="POST" action="/home">
    <input type="hidden" name="username" value="{safe_username}">
  </form>
  <script>
    document.getElementById('homeRedirectForm').submit();
  </script>
</body>
</html>
"""
    return html


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login_route():
    username = request.form["username"]
    password = request.form["password"]
    user = db_login(username, password)
    if user:
        session["username"] = username.strip()
        return jsonify({"ok": True, "message": "Login successful."})
    return jsonify({"ok": False, "error": "Invalid username or password."}), 401


@app.route("/usernameExist", methods=["POST"])
def username_exist_route():
    username = request.form.get("username", "").strip()
    if not username:
        return jsonify({"usernameExists": False})
    return jsonify({"usernameExists": check_username_exists(username)})


@app.route("/signup", methods=["POST"])
def signup_route():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return jsonify({"ok": False, "error": "Username, password, and Gmail are required."}), 400

    if check_username_exists(username):
        return jsonify({"ok": False, "error": "That username already exists."}), 409

    db_signup(username, password)
    session["username"] = username
    return jsonify({"ok": True, "message": "Signup complete."})

@app.route("/home", methods=["POST"])
def home():
    username = request.form.get("username", "").strip() or session.get("username", "").strip()
    if username:
        session["username"] = username
    videos = get_videos_by_username(username) if username else []
    tokens = get_auth_tokens(username) if username else {}
    youtube_connected = bool(tokens and isinstance(tokens, dict) and tokens.get("youtube"))
    home_data = _build_home_data(username, videos, youtube_connected=youtube_connected)
    return render_template("home.html", home_data=home_data)


@app.route("/auth/youtube/start", methods=["POST", "GET"])
def youtube_auth_start():
    username = (
        request.form.get("username", "").strip()
        or request.args.get("username", "").strip()
        or session.get("username", "").strip()
    )
    if not username:
        return jsonify({"ok": False, "error": "No active user in session."}), 400

    if not os.path.exists(YOUTUBE_CLIENT_SECRETS_FILE):
        return jsonify({"ok": False, "error": "YouTube OAuth client secret file not found."}), 500
    if not YOUTUBE_REDIRECT_URI:
        return jsonify({"ok": False, "error": "No redirect URI found in OAuth client secret JSON."}), 500

    flow = Flow.from_client_secrets_file(
        YOUTUBE_CLIENT_SECRETS_FILE,
        scopes=YOUTUBE_OAUTH_SCOPES,
        redirect_uri=YOUTUBE_REDIRECT_URI,
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["youtube_oauth_state"] = state
    session["oauth_username"] = username
    return redirect(authorization_url)


@app.route("/auth/youtube/callback", methods=["GET"])
def youtube_auth_callback():
    state = request.args.get("state", "")
    stored_state = session.get("youtube_oauth_state", "")
    if not state or state != stored_state:
        return jsonify({"ok": False, "error": "OAuth state validation failed."}), 400

    flow = Flow.from_client_secrets_file(
        YOUTUBE_CLIENT_SECRETS_FILE,
        scopes=YOUTUBE_OAUTH_SCOPES,
        state=stored_state,
        redirect_uri=YOUTUBE_REDIRECT_URI,
    )
    flow.fetch_token(authorization_response=request.url)
    username = session.get("oauth_username", "").strip() or session.get("username", "").strip()
    if not username:
        return jsonify({"ok": False, "error": "Unable to map OAuth callback to a user."}), 400

    existing_tokens = get_auth_tokens(username) or {}
    if not isinstance(existing_tokens, dict):
        existing_tokens = {}
    existing_tokens["youtube"] = _credentials_to_dict(flow.credentials)

    if not update_auth_tokens(username, existing_tokens):
        return jsonify({"ok": False, "error": "Could not save OAuth tokens for this user."}), 500

    session["username"] = username
    return _home_post_redirect_response(username)


@app.route("/publish/youtube", methods=["POST"])
def youtube_publish_route():
    username = request.form.get("username", "").strip() or session.get("username", "").strip()
    if not username:
        return jsonify({"ok": False, "error": "No active user in session."}), 400

    video_path = request.form.get("video_path", "").strip()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    privacy_status = request.form.get("privacy_status", "private").strip() or "private"
    raw_tags = request.form.get("tags", "").strip()
    tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]

    try:
        response = publish_to_youtube(
            username=username,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
        )
        return jsonify({
            "ok": True,
            "message": "Video published to YouTube.",
            "youtube_video_id": response.get("id"),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/auth/youtube/debug", methods=["GET"])
def youtube_auth_debug():
    return jsonify({
        "client_id": YOUTUBE_OAUTH_CLIENT_CONFIG.get("client_id"),
        "redirect_uri_in_use": YOUTUBE_REDIRECT_URI,
        "client_secrets_file": YOUTUBE_CLIENT_SECRETS_FILE,
    })

if __name__ == "__main__":
    app.run(debug=True)
