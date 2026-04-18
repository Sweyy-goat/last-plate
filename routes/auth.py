from flask import Blueprint, request, jsonify
from utils.db import mysql
from utils.security import hash_password, verify_password
from app import limiter
import MySQLdb.cursors
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

auth_bp = Blueprint("auth", __name__)

# ================= USER PROFILE API =================
@auth_bp.route("/api/user/profile", methods=["GET"])
@jwt_required()
def user_profile():
    current_user_id = get_jwt_identity()

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT name, email, mobile
        FROM users
        WHERE id = %s
    """, (current_user_id,))

    user = cur.fetchone()

    if not user:
        return jsonify({
            "status": "error",
            "message": "User not found"
        }), 404
        
    return jsonify({
        "status": "success",
        "data": user
    })


# ================= USER ORDER HISTORY API =================
@auth_bp.route("/api/user/orders", methods=["GET"])
@jwt_required()
def user_orders():
    current_user_id = get_jwt_identity()

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
    """, (current_user_id,))

    orders = cur.fetchall()

    return jsonify({
        "status": "success",
        "data": orders
    })


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
        return jsonify({
            "status": "error",
            "message": "All fields required"
        }), 400

    cur = mysql.connection.cursor()

    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        return jsonify({
            "status": "error",
            "message": "Email already exists"
        }), 400

    cur.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    if cur.fetchone():
        return jsonify({
            "status": "error",
            "message": "Mobile already exists"
        }), 400

    password_hash = hash_password(password)

    cur.execute("""
        INSERT INTO users (name, email, mobile, password_hash)
        VALUES (%s, %s, %s, %s)
    """, (name, email, mobile, password_hash))

    mysql.connection.commit()

    return jsonify({
        "status": "success",
        "message": "User created"
    })


# ================= USER LOGIN =================
@auth_bp.route("/api/user/login", methods=["POST"])
@limiter.limit("5 per minute")
def user_login():
    data = request.get_json(silent=True) or {}

    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({
            "status": "error",
            "message": "Missing credentials"
        }), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        "SELECT id, password_hash FROM users WHERE mobile=%s",
        (mobile,)
    )
    user = cur.fetchone()

    if not user:
        return jsonify({
            "status": "error",
            "message": "User not found"
        }), 401

    if not verify_password(user["password_hash"], password):
        return jsonify({
            "status": "error",
            "message": "Invalid password"
        }), 401

    access_token = create_access_token(identity=user["id"])

    return jsonify({
        "status": "success",
        "access_token": access_token,
        "user_id": user["id"],
        "role": "user"
    })


# ================= RESTAURANT LOGIN =================
@auth_bp.route("/api/restaurant/login", methods=["POST"])
@limiter.limit("5 per minute")
def restaurant_login():
    data = request.get_json(silent=True) or {}

    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({
            "status": "error",
            "message": "Missing credentials"
        }), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        "SELECT id, password_hash FROM restaurants WHERE mobile=%s AND is_active=1",
        (mobile,)
    )
    restaurant = cur.fetchone()

    if not restaurant:
        return jsonify({
            "status": "error",
            "message": "Restaurant not found"
        }), 401

    if not verify_password(restaurant["password_hash"], password):
        return jsonify({
            "status": "error",
            "message": "Invalid password"
        }), 401

    access_token = create_access_token(identity=restaurant["id"])

    return jsonify({
        "status": "success",
        "access_token": access_token,
        "restaurant_id": restaurant["id"],
        "role": "restaurant"
    })
