from flask import Blueprint, jsonify
from utils.db import mysql
from MySQLdb.cursors import DictCursor

secret_bp = Blueprint("secret", __name__)


# ============================================================
# 1️⃣ GET RESTAURANTS THAT HAVE ACTIVE SECRET MENU TODAY
# ============================================================
@secret_bp.route("/api/secret-menu/restaurants", methods=["GET"])
def secret_restaurants():
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT 
            r.id AS restaurant_id,
            r.name AS restaurant_name,
            r.address,
            COUNT(sm.id) AS dish_count,
            MIN(sm.price) AS min_price,
            MAX(sm.price) AS max_price
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        WHERE 
            sm.stock > 0
            AND sm.is_today_special = 1
        GROUP BY r.id
        ORDER BY r.name ASC
    """)

    items = cur.fetchall()

    return jsonify({
        "success": True,
        "restaurants": items
    })


# ============================================================
# 2️⃣ GET ALL SECRET DISHES OF ONE RESTAURANT (only today's active)
# ============================================================
@secret_bp.route("/api/secret-menu/<int:rid>", methods=["GET"])
def secret_menu_by_restaurant(rid):
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT 
            sm.id,
            sm.name,
            sm.cuisine,
            sm.description,
            sm.price,
            sm.mrp,
            sm.stock,
            sm.img,
            r.name AS restaurant_name
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        WHERE 
            sm.restaurant_id = %s
            AND sm.stock > 0
            AND sm.is_today_special = 1
        ORDER BY sm.id DESC
    """, (rid,))

    dishes = cur.fetchall()

    return jsonify({
        "success": True,
        "dishes": dishes
    })
# ================= CREATE SECRET ORDER =================
@secret_bp.route("/api/secret/create-order", methods=["POST"])
def create_secret_order():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    dish_id = int(data["dish_id"])
    qty = int(data["quantity"])
    user_phone = data["phone"]
    user_email = data["email"]

    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT price, restaurant_id, stock
        FROM secret_menu
        WHERE id=%s
        FOR UPDATE
    """, (dish_id,))
    dish = cur.fetchone()

    if not dish or dish["stock"] < qty:
        return jsonify({"error": "Insufficient stock"}), 400

    base_price = float(dish["price"])
    final_unit_price = math.ceil(base_price * 1.18)
    amount_paise = final_unit_price * qty * 100

    rp_order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    cur.execute("""
        INSERT INTO secret_orders
        (user_id, dish_id, restaurant_id, quantity,
         user_phone, user_email, total_amount,
         status, payment_status, razorpay_order_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'PENDING','PENDING',%s)
    """, (
        session["user_id"], dish_id, dish["restaurant_id"], qty,
        user_phone, user_email, final_unit_price * qty,
        rp_order["id"]
    ))

    mysql.connection.commit()

    return jsonify({
        "razorpay_order_id": rp_order["id"],
        "amount": amount_paise,
        "key": os.getenv("RAZORPAY_KEY_ID")
    })
