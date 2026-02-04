from flask import Blueprint, render_template, request, jsonify, session, redirect
from utils.db import mysql
import MySQLdb.cursors
import random

restaurant_bp = Blueprint("restaurant", __name__, url_prefix="/restaurant")

def restaurant_required():
    return session.get("role") == "restaurant"

# -----------------------------
# LOGIN PAGE (STEP 1)
# -----------------------------
@restaurant_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("restaurant/login.html")


# -----------------------------
# SEND OTP API (STEP 2)
# -----------------------------
@restaurant_bp.route("/api/send-otp", methods=["POST"])
def send_otp():
    phone = request.json.get("mobile")

    if not phone:
        return jsonify({"success": False, "error": "Mobile number required"}), 400

    otp = random.randint(100000, 999999)

    session["otp"] = otp
    session["otp_mobile"] = phone

    # TODO: Replace with SMS API (MSG91, Fast2SMS, Twilio, etc.)
    print("RESTAURANT OTP:", otp)

    return jsonify({"success": True})


# -----------------------------
# VERIFY OTP PAGE (STEP 3)
# -----------------------------
@restaurant_bp.route("/verify-otp", methods=["GET"])
def verify_otp_page():
    return render_template("restaurant/verify_otp.html")


# -----------------------------
# VERIFY OTP API (STEP 4)
# -----------------------------
@restaurant_bp.route("/api/verify-otp", methods=["POST"])
def verify_otp():
    user_otp = request.json.get("otp")

    if str(user_otp) != str(session.get("otp")):
        return jsonify({"success": False, "error": "Invalid OTP"}), 400

    phone = session.get("otp_mobile")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if restaurant already exists
    cur.execute("SELECT id FROM restaurants WHERE mobile=%s", (phone,))
    row = cur.fetchone()

    if not row:
        # Create new restaurant
        cur.execute("""
            INSERT INTO restaurants (name, mobile, is_active)
            VALUES (%s, %s, 1)
        """, ("Restaurant", phone))
        mysql.connection.commit()
        restaurant_id = cur.lastrowid
    else:
        restaurant_id = row["id"]

    # LOGIN SUCCESS
    session["restaurant_id"] = restaurant_id
    session["role"] = "restaurant"

    return jsonify({"success": True})


# -----------------------------
# DASHBOARD
# -----------------------------
@restaurant_bp.route("/dashboard")
def dashboard():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/dashboard.html")


# -----------------------------
# ADD FOOD PAGE
# -----------------------------
@restaurant_bp.route("/add-food")
def add_food_page():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/add_food.html")


# -----------------------------
# ADD FOOD API
# -----------------------------
@restaurant_bp.route("/api/add-food", methods=["POST"])
def add_food():
    if not restaurant_required():
        return jsonify({"success": False}), 401

    data = request.json
    restaurant_id = session["restaurant_id"]

    try:
        price = int(data.get("price"))
        original_price = int(data.get("original_price"))
        quantity = int(data.get("quantity"))
    except:
        return jsonify({"error": "Invalid numeric values"}), 400

    if price <= 0 or quantity <= 0:
        return jsonify({"error": "Invalid price or quantity"}), 400

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO foods
        (restaurant_id, name, original_price, price,
         available_quantity, pickup_start, pickup_end, is_active, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,1, CONVERT_TZ(NOW(), '+00:00', '+05:30'))
    """, (
        restaurant_id,
        data["name"],
        original_price,
        price,
        quantity,
        data["pickup_start"],
        data["pickup_end"]
    ))

    mysql.connection.commit()
    return jsonify({"success": True})


# -----------------------------
# GET MY FOODS
# -----------------------------
@restaurant_bp.route("/api/my-foods")
def my_foods():
    if not restaurant_required():
        return jsonify([]), 401

    restaurant_id = session["restaurant_id"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT
            id,
            name,
            price,
            available_quantity,
            pickup_start,
            pickup_end,
            is_active
        FROM foods
        WHERE restaurant_id = %s
        ORDER BY pickup_end ASC
    """, (restaurant_id,))

    rows = cur.fetchall()

    foods = []
    for f in rows:
        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": f["price"],
            "available_quantity": f["available_quantity"],
            "pickup_start": str(f["pickup_start"]),
            "pickup_end": str(f["pickup_end"]),
            "is_active": bool(f["is_active"])
        })

    return jsonify(foods)


# -----------------------------
# CANCEL FOOD
# -----------------------------
@restaurant_bp.route("/api/cancel-food/<int:food_id>", methods=["POST"])
def cancel_food(food_id):
    if not restaurant_required():
        return jsonify({"success": False}), 401

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE foods
        SET is_active = 0
        WHERE id = %s AND restaurant_id = %s
    """, (food_id, session["restaurant_id"]))

    mysql.connection.commit()
    return jsonify({"success": True})


# -----------------------------
# UPDATE FOOD QUANTITY
# -----------------------------
@restaurant_bp.route("/api/update-food-quantity/<int:food_id>", methods=["POST"])
def update_food_quantity(food_id):
    if not restaurant_required():
        return jsonify({"success": False}), 401

    data = request.json
    new_qty = int(data["quantity"])

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE foods
        SET available_quantity = %s,
            is_active = IF(%s > 0, 1, 0)
        WHERE id = %s AND restaurant_id = %s
    """, (new_qty, new_qty, food_id, session["restaurant_id"]))

    mysql.connection.commit()
    return jsonify({"success": True})
