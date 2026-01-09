from flask import Blueprint, request, jsonify, session, render_template, redirect
from utils.db import mysql
from utils.security import hash_password, verify_password

auth_bp = Blueprint("auth", __name__)

# ---------------- USER PAGES ----------------
@auth_bp.route("/login")
def user_login_page():
    return render_template("auth/user_login.html")

@auth_bp.route("/signup")
def user_signup_page():
    return render_template("auth/user_signup.html")

# ---------------- RESTAURANT PAGE ----------------
@auth_bp.route("/restaurant/login")
def restaurant_login_page():
    return render_template("auth/restaurant_login.html")

# ---------------- USER SIGNUP ----------------
@auth_bp.route("/api/user/signup", methods=["POST"])
def user_signup():
    data = request.json
    name = data["name"]
    mobile = data["mobile"]
    password = data["password"]

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    if cur.fetchone():
        return jsonify({"success": False, "message": "Mobile already exists"}), 400

    hashed = hash_password(password)

    cur.execute(
        "INSERT INTO users (name, mobile, password_hash) VALUES (%s,%s,%s)",
        (name, mobile, hashed)
    )
    mysql.connection.commit()

    return jsonify({"success": True})

# ---------------- USER LOGIN ----------------
@auth.route("/api/user/login", methods=["POST"])
def user_login():
    data = request.json
    mobile = data.get("mobile")
    password = data.get("password")

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, password_hash FROM users WHERE mobile=%s",
        (mobile,)
    )
    user = cur.fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 401

    if not verify_password(user["password_hash"], password):
        return jsonify({"error": "Invalid password"}), 401

    return jsonify({
        "success": True,
        "user_id": user["id"]
    })


# ---------------- RESTAURANT LOGIN ----------------
@auth_bp.route("/api/restaurant/login", methods=["POST"])
def restaurant_login():
    data = request.json
    mobile = data["mobile"]
    password = data["password"]

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, password_hash FROM restaurants WHERE mobile=%s AND is_active=1",
        (mobile,)
    )
    restaurant = cur.fetchone()

    if restaurant and verify_password(restaurant[1], password):
        session.clear()
        session["restaurant_id"] = restaurant[0]
        session["role"] = "restaurant"
        return jsonify({"success": True})

    return jsonify({"success": False}), 401

# ---------------- LOGOUT ----------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
