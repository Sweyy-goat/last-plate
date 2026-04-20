from flask import Blueprint, request, jsonify, session, render_template, redirect
from utils.db import mysql
from utils.security import hash_password, verify_password
from app import limiter
import MySQLdb.cursors

# ✅ Import JWT tools
from flask_jwt_extended import create_access_token

auth_bp = Blueprint("auth", __name__)


# ================= USER PAGES =================
@auth_bp.route("/login")
@limiter.limit("5 per minute")
def user_login_page():
    return render_template("auth/user_login.html")

@auth_bp.route("/signup")
def user_signup_page():
    return render_template("auth/user_signup.html")


# ================= RESTAURANT PAGE =================
@auth_bp.route("/restaurant/login")
def restaurant_login_page():
    return render_template("auth/restaurant_login.html")


# ================= USER PROFILE API =================
@auth_bp.route("/api/user/profile")
def user_profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT name, email, mobile
        FROM users
        WHERE id = %s
    """, (session["user_id"],))

    user = cur.fetchone()
    cur.close()
    return jsonify(user)


# ================= USER ORDER HISTORY API =================
@auth_bp.route("/api/user/orders")
def user_orders():
    if "user_id" not in session:
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
    """, (session["user_id"],))

    result = cur.fetchall()
    cur.close()
    return jsonify(result)


# ================= USER SIGNUP =================
@auth_bp.route("/api/user/signup", methods=["POST"])
def user_signup():
    data = request.json

    name = data.get("name")
    email = data.get("email")
    mobile = data.get("mobile")
    password = data.get("password")

    if not name or not email or not mobile or not password:
        return jsonify({"error": "All fields required"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "Email already exists"}), 400

    cur.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "Mobile already exists"}), 400

    password_hash = hash_password(password)

    cur.execute("""
        INSERT INTO users (name, email, mobile, password_hash)
        VALUES (%s, %s, %s, %s)
    """, (name, email, mobile, password_hash))

    mysql.connection.commit()
    cur.close()

    return jsonify({"success": True})


# ================= USER LOGIN =================
@auth_bp.route("/api/user/login", methods=["POST"])
def user_login():
    data = request.json
    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({"error": "Missing credentials"}), 400

    # ✅ FIX: Use DictCursor so user["password_hash"] works
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        "SELECT id, password_hash FROM users WHERE mobile=%s",
        (mobile,)
    )
    user = cur.fetchone()
    cur.close()

    if not user:
        return jsonify({"error": "User not found"}), 401

    if not verify_password(user["password_hash"], password):
        return jsonify({"error": "Invalid password"}), 401

    # ✅ FIX: Set session (for web) AND return JWT token (for mobile)
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "user"

    # ✅ Create JWT — identity must be a string for flask_jwt_extended
    access_token = create_access_token(identity=str(user["id"]))

    return jsonify({
        "success": True,
        "access_token": access_token,   # ← mobile app uses this
        "user_id": user["id"]
    })


# ================= RESTAURANT LOGIN =================
@auth_bp.route("/api/restaurant/login", methods=["POST"])
def restaurant_login():
    data = request.json
    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({"error": "Missing credentials"}), 400

    # ✅ FIX: Use DictCursor
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        "SELECT id, password_hash FROM restaurants WHERE mobile=%s AND is_active=1",
        (mobile,)
    )
    restaurant = cur.fetchone()
    cur.close()

    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 401

    if not verify_password(restaurant["password_hash"], password):
        return jsonify({"error": "Invalid password"}), 401

    session.clear()
    session["restaurant_id"] = restaurant["id"]
    session["role"] = "restaurant"

    # ✅ Issue JWT for restaurant too
    access_token = create_access_token(identity=str(restaurant["id"]))

    return jsonify({
        "success": True,
        "access_token": access_token,
        "restaurant_id": restaurant["id"]
    })


# ================= LOGOUT =================
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
