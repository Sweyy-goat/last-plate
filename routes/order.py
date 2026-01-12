from flask import Blueprint, render_template, request, jsonify, session, redirect
from utils.db import mysql
import MySQLdb.cursors
import razorpay
import os

order_bp = Blueprint("order", __name__)

# ================= RAZORPAY CLIENT =================
razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# ================= CHECKOUT PAGE =================
@order_bp.route("/checkout/<int:food_id>")
def checkout(food_id):
    if "user_id" not in session or session.get("role") != "user":
        return redirect("/login")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT
            f.id,
            f.name,
            f.price,
            f.available_quantity,
            r.name AS restaurant_name
        FROM foods f
        JOIN restaurants r ON f.restaurant_id = r.id
        WHERE f.id = %s AND f.is_active = 1
    """, (food_id,))

    food = cur.fetchone()

    if not food:
        return "Food not found", 404

    if food["available_quantity"] <= 0:
        return "Sold out", 400

    return render_template("checkout.html", food=food)


# ================= CREATE RAZORPAY ORDER =================
@order_bp.route("/api/create-order", methods=["POST"])
def create_order():
    if "user_id" not in session or session.get("role") != "user":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    food_id = int(data.get("food_id"))
    quantity = int(data.get("quantity"))

    if quantity <= 0:
        return jsonify({"error": "Invalid quantity"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 🔒 LOCK FOOD ROW
    cur.execute("""
        SELECT id, restaurant_id, price, available_quantity
        FROM foods
        WHERE id = %s
        FOR UPDATE
    """, (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] < quantity:
        return jsonify({"error": "Not enough quantity"}), 400

    amount_paise = food["price"] * quantity * 100  # Razorpay uses paise

    # ✅ CREATE RAZORPAY ORDER
    razorpay_order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    # ✅ SAVE ORDER (DO NOT REDUCE STOCK YET)
    cur.execute("""
        INSERT INTO orders
        (user_id, food_id, quantity, restaurant_id,
         total_amount, status, payment_status, razorpay_order_id)
        VALUES (%s, %s, %s, %s, %s, 'PENDING', 'PENDING', %s)
    """, (
        session["user_id"],
        food_id,
        quantity,
        food["restaurant_id"],
        amount_paise / 100,
        razorpay_order["id"]
    ))

    mysql.connection.commit()

    return jsonify({
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount_paise,
        "key": os.getenv("RAZORPAY_KEY_ID")
    })


# ================= VERIFY PAYMENT =================
@order_bp.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json

    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_signature = data.get("razorpay_signature")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 🔐 VERIFY SIGNATURE
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_signature": razorpay_signature
        })
    except:
        # ❌ MARK ORDER FAILED
        cur.execute("""
            UPDATE orders
            SET status='FAILED', payment_status='FAILED'
            WHERE razorpay_order_id=%s
        """, (razorpay_order_id,))
        mysql.connection.commit()
        return jsonify({"success": False}), 400

    # 🔒 LOCK ORDER ROW
    cur.execute("""
        SELECT id, food_id, quantity
        FROM orders
        WHERE razorpay_order_id=%s AND payment_status='PENDING'
        FOR UPDATE
    """, (razorpay_order_id,))
    order = cur.fetchone()

    if not order:
        return jsonify({"success": False}), 400

    # 🔒 SAFE STOCK REDUCTION
    cur.execute("""
        UPDATE foods
        SET available_quantity = available_quantity - %s
        WHERE id = %s AND available_quantity >= %s
    """, (
        order["quantity"],
        order["food_id"],
        order["quantity"]
    ))

    if cur.rowcount == 0:
        return jsonify({"success": False, "error": "Stock issue"}), 409

    # ✅ MARK ORDER PAID
    cur.execute("""
        UPDATE orders
        SET payment_status='PAID',
            status='CONFIRMED',
            razorpay_payment_id=%s
        WHERE id=%s
    """, (razorpay_payment_id, order["id"]))

    mysql.connection.commit()

    return jsonify({"success": True})
