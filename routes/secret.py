from flask import Blueprint, jsonify, session, redirect, render_template, request
from utils.db import mysql
from MySQLdb.cursors import DictCursor
import math, os
import razorpay
from utils.emailer import send_email

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

    cur = mysql.connection.cursor(DictCursor)

    # 🔹 Fetch USER EMAIL directly from DB
    cur.execute("SELECT email FROM users WHERE id=%s", (session["user_id"],))
    u = cur.fetchone()
    user_email = u["email"]

    # Get dish
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
    final_unit_price = math.ceil(base_price * 1.18)   # 18% fee
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
        user_phone, user_email,
        final_unit_price * qty,
        rp_order["id"]
    ))

    mysql.connection.commit()

    return jsonify({
        "razorpay_order_id": rp_order["id"],
        "amount": amount_paise,
        "key": os.getenv("RAZORPAY_KEY_ID")
    })
# ================= VERIFY SECRET PAYMENT =================
@secret_bp.route("/api/secret/verify-payment", methods=["POST"])
def secret_verify_payment():
    data = request.json
    cur = mysql.connection.cursor(DictCursor)

    try:
        razorpay_client.utility.verify_payment_signature(data)
    except:
        return jsonify({"success": False}), 400

    cur.execute("""
        SELECT so.*, sm.name AS dish_name, sm.price AS base_price,
               r.name AS restaurant_name, r.email AS res_email,
               r.location_link AS res_location
        FROM secret_orders so
        JOIN secret_menu sm ON so.dish_id = sm.id
        JOIN restaurants r ON sm.restaurant_id = r.id
        WHERE so.razorpay_order_id=%s
          AND so.payment_status='PENDING'
        FOR UPDATE
    """, (data["razorpay_order_id"],))
    order = cur.fetchone()

    if not order:
        return jsonify({"success": False}), 400

    qty = order["quantity"]

    cur.execute("""
        UPDATE secret_menu
        SET stock = stock - %s
        WHERE id=%s AND stock >= %s
    """, (qty, order["dish_id"], qty))

    if cur.rowcount == 0:
        mysql.connection.rollback()
        return jsonify({"success": False, "error": "Out of stock"}), 409

    cur.execute("""
        UPDATE secret_orders
        SET payment_status='PAID',
            status='CONFIRMED',
            razorpay_payment_id=%s
        WHERE id=%s
    """, (data["razorpay_payment_id"], order["id"]))

    mysql.connection.commit()

    collected = float(order["total_amount"])
    restaurant_payout = float(order["base_price"]) * qty

    # ---- Email restaurant ----
    send_email(
        order["res_email"],
        f"Secret Menu Order: {order['dish_name']}",
        f"""
        <h2>New Secret Order</h2>
        <p><b>Dish:</b> {order['dish_name']}</p>
        <p><b>Quantity:</b> {qty}</p>

        <h3>Customer Phone Number</h3>
        <h1>{order['user_phone']}</h1>

        <p>Restaurant Payout: ₹{restaurant_payout}</p>

        <a href="{order['res_location']}">Open in Maps</a>
        """
    )

    # ---- Email user ----
    send_email(
        order["user_email"],
        "Your Secret Menu Order is Confirmed",
        f"""
        <h2>Order Confirmed!</h2>
        <p>You ordered: <b>{order['dish_name']}</b> × {qty}<br>
        Show your phone number (<b>{order['user_phone']}</b>) at pickup.</p>

        <a href="{order['res_location']}">Open in Google Maps</a>
        """
    )

    # ---- Email admin ----
    send_email(
        "terminalplate@gmail.com",
        f"Secret Order Report: {order['dish_name']}",
        f"""
        Dish: {order['dish_name']}<br>
        Qty: {qty}<br>
        Phone: {order['user_phone']}<br>
        Charged: ₹{collected}<br>
        Payout: ₹{restaurant_payout}<br>
        Profit: ₹{collected - restaurant_payout}
        """
    )

    return jsonify({"success": True})
@secret_bp.route("/checkout/secret/<int:dish_id>")
def secret_checkout(dish_id):
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor(DictCursor)
    cur.execute("""
        SELECT sm.id, sm.name, sm.price, sm.stock, r.name AS restaurant_name
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        WHERE sm.id=%s AND sm.stock > 0
    """, (dish_id,))
    
    dish = cur.fetchone()
    if not dish:
        return "Not available", 404

    return render_template("user/secret_checkout.html", dish=dish)
