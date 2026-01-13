from flask import Blueprint, request, jsonify, session, render_template, redirect
from utils.db import mysql
from utils.security import hash_password, verify_password

auth_bp = Blueprint("auth", __name__)

# ================= USER PAGES =================
@auth_bp.route("/login")
def user_login_page():
    return render_template("auth/user_login.html")

@auth_bp.route("/signup")
def user_signup_page():
    return render_template("auth/user_signup.html")

# ================= RESTAURANT PAGE =================
@auth_bp.route("/restaurant/login")
def restaurant_login_page():
    return render_template("auth/restaurant_login.html")

# ================= USER SIGNUP =================
# ================= USER SIGNUP =================
@auth_bp.route("/api/user/signup", methods=["POST"])
def user_signup():
    data = request.json

    name = data.get("name")
    email = data.get("email")          # ✅ FIX
    mobile = data.get("mobile")
    password = data.get("password")

    if not name or not email or not mobile or not password:
        return jsonify({"error": "All fields required"}), 400

    cur = mysql.connection.cursor()

    # ❌ Check duplicate email
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        return jsonify({"error": "Email already exists"}), 400

    # ❌ Check duplicate mobile
    cur.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    if cur.fetchone():
        return jsonify({"error": "Mobile already exists"}), 400

    password_hash = hash_password(password)  # ✅ FIX

    cur.execute("""
        INSERT INTO users (name, email, mobile, password_hash)
        VALUES (%s, %s, %s, %s)
    """, (
        name,
        email,
        mobile,
        password_hash
    ))

    mysql.connection.commit()

    return jsonify({"success": True})


# ================= USER LOGIN =================
@auth_bp.route("/api/user/login", methods=["POST"])
def user_login():
    data = request.json
    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({"error": "Missing credentials"}), 400

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

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "user"

    return jsonify({"success": True})

# ================= RESTAURANT LOGIN =================
@auth_bp.route("/api/restaurant/login", methods=["POST"])
def restaurant_login():
    data = request.json
    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({"error": "Missing credentials"}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, password_hash FROM restaurants WHERE mobile=%s AND is_active=1",
        (mobile,)
    )
    restaurant = cur.fetchone()

    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 401

    if not verify_password(restaurant["password_hash"], password):
        return jsonify({"error": "Invalid password"}), 401

    session.clear()
    session["restaurant_id"] = restaurant["id"]
    session["role"] = "restaurant"

    return jsonify({"success": True})

# ================= LOGOUT =================
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

