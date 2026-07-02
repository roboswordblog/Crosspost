from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from datamanagement import (
    login as db_login,
    signup as db_signup,
    check_username_exists,
    get_videos_by_username,
)

app = Flask(__name__)


def _parse_date(value):
    if not value:
        return None
    date_portion = str(value).strip()[:10]
    try:
        return datetime.strptime(date_portion, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_home_data(username, videos):
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login_route():
    username = request.form["username"]
    password = request.form["password"]
    user = db_login(username, password)
    if user:
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
    return jsonify({"ok": True, "message": "Signup complete."})

@app.route("/home", methods=["POST", "GET"])
def home():
    username = (
        request.args.get("username", "").strip()
        or request.form.get("username", "").strip()
    )
    videos = get_videos_by_username(username) if username else []
    home_data = _build_home_data(username, videos)
    return render_template("home.html", home_data=home_data)

if __name__ == "__main__":
    app.run(debug=True)
