from flask import Blueprint, request, jsonify, session, render_template, redirect
from utils.db import mysql
from utils.security import hash_password, verify_password
from app import limiter

import MySQLdb.cursors

# 🔥 JWT
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity
)

auth_bp = Blueprint("auth", __name__)


# ================= WEB PAGES =================

@auth_bp.route("/login")
@limiter.limit("5 per minute")
def user_login_page():
    return render_template("auth/user_login.html")


@auth_bp.route("/signup")
def user_signup_page():
    return render_template("auth/user_signup.html")


@auth_bp.route("/restaurant/login")
def restaurant_login_page():
    return render_template("auth/restaurant_login.html")


# ================= USER SIGNUP =================

@auth_bp.route("/api/user/signup", methods=["POST"])
@limiter.limit("3 per minute")
def user_signup():
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    email = data.get("email")
    mobile = data.get("mobile")
    password = data.get("password")

    if not name or not email or not mobile or not password:
        return jsonify({"error": "All fields required"}), 400

    cur = mysql.connection.cursor()

    # Duplicate checks
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        return jsonify({"error": "Email already exists"}), 400

    cur.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    if cur.fetchone():
        return jsonify({"error": "Mobile already exists"}), 400

    password_hash = hash_password(password)

    cur.execute("""
        INSERT INTO users (name, email, mobile, password_hash)
        VALUES (%s, %s, %s, %s)
    """, (name, email, mobile, password_hash))

    mysql.connection.commit()

    return jsonify({"success": True})


# ================= USER LOGIN (HYBRID) =================

@auth_bp.route("/api/user/login", methods=["POST"])
@limiter.limit("5 per minute")
def user_login():
    data = request.get_json(silent=True) or {}

    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({"error": "Missing credentials"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        "SELECT id, password_hash FROM users WHERE mobile=%s",
        (mobile,)
    )
    user = cur.fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 401

    if not verify_password(user["password_hash"], password):
        return jsonify({"error": "Invalid password"}), 401

    # 🔥 Detect client type
    is_api = request.headers.get("Content-Type") == "application/json"

    if is_api:
        # 📱 Flutter → JWT
        token = create_access_token(identity=user["id"])
        return jsonify({
            "success": True,
            "access_token": token,
            "user_id": user["id"]
        })
    else:
        # 🌐 Website → session
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = "user"
        return redirect("/")


# ================= USER PROFILE =================

@auth_bp.route("/api/user/profile", methods=["GET"])
def user_profile():
    # 🔥 Try JWT first (mobile)
    try:
        user_id = get_jwt_identity()
    except:
        user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT name, email, mobile
        FROM users
        WHERE id = %s
    """, (user_id,))

    return jsonify(cur.fetchone())


# ================= USER ORDERS =================

@auth_bp.route("/api/user/orders", methods=["GET"])
def user_orders():
    try:
        user_id = get_jwt_identity()
    except:
        user_id = session.get("user_id")

    if not user_id:
        return jsonify([])

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT
            f.name AS food,
            o.quantity,
            o.total_amount,
            o.status
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        WHERE o.user_id = %s
        ORDER BY o.id DESC
    """, (user_id,))

    return jsonify(cur.fetchall())


# ================= RESTAURANT LOGIN =================

@auth_bp.route("/api/restaurant/login", methods=["POST"])
@limiter.limit("5 per minute")
def restaurant_login():
    data = request.get_json(silent=True) or {}

    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({"error": "Missing credentials"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        "SELECT id, password_hash FROM restaurants WHERE mobile=%s AND is_active=1",
        (mobile,)
    )
    restaurant = cur.fetchone()

    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 401

    if not verify_password(restaurant["password_hash"], password):
        return jsonify({"error": "Invalid password"}), 401

    token = create_access_token(identity=restaurant["id"])

    return jsonify({
        "success": True,
        "access_token": token,
        "restaurant_id": restaurant["id"]
    })


# ================= LOGOUT =================

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
