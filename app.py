from flask import Flask, render_template, jsonify, request
from datamanagement import *
from payments import *
from publishing import *

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]


@app.route("/usernameExist", methods=["POST"])
def usernameExist():
    username = request.form["username"]
    return {"usernameExists": usernameExist(username)}


@app.route("/signup", methods=["POST"])
def signup():
    username = request.form["username"]
    password = request.form["password"]


app.run(debug=True)
