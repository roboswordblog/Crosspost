from flask import Flask, render_template, request, jsonify
from datamanagement import login as db_login, signup as db_signup, check_username_exists

app = Flask(__name__)


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

if __name__ == "__main__":
    app.run(debug=True)
