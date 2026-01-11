from flask import Blueprint, render_template, request, jsonify, session, redirect, current_app
from utils.db import mysql
import MySQLdb.cursors
import razorpay
import random

order_bp = Blueprint("order", __name__)

def razorpay_client():
    return razorpay.Client(auth=(
        current_app.config["rzp_test_S2bmctosdabOoM"],
        current_app.config["77RfmWU2bJoKhsAknuxti9bi"]
    ))

# ---------------- CHECKOUT PAGE ----------------
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
        WHERE f.id=%s AND f.is_active=1
    """, (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] <= 0:
        return "Food not available", 404

    return render_template("checkout.html", food=food)

# ---------------- CREATE ORDER + RAZORPAY ORDER ----------------
@order_bp.route("/api/order/create", methods=["POST"])
def create_order():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    food_id = int(data["food_id"])
    quantity = int(data["quantity"])

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 🔒 lock food row
    cur.execute("""
        SELECT id, restaurant_id, price, available_quantity
        FROM foods
        WHERE id=%s
        FOR UPDATE
    """, (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] < quantity:
        return jsonify({"error": "Not enough stock"}), 400

    amount_rupees = food["price"] * quantity
    amount_paise = amount_rupees * 100

    # Razorpay order
    rp = razorpay_client()
    rp_order = rp.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    # Reduce quantity
    cur.execute("""
        UPDATE foods
        SET available_quantity = available_quantity - %s
        WHERE id=%s
    """, (quantity, food_id))

    otp = random.randint(100000, 999999)

    # Insert order
    cur.execute("""
        INSERT INTO orders
        (user_id, restaurant_id, total_amount,
         razorpay_order_id, status, payment_status, otp, created_at)
        VALUES (%s,%s,%s,%s,'PENDING','PENDING',%s,NOW())
    """, (
        session["user_id"],
        food["restaurant_id"],
        amount_rupees,
        rp_order["id"],
        otp
    ))

    mysql.connection.commit()

    return jsonify({
        "key": current_app.config["RAZORPAY_KEY_ID"],
        "razorpay_order_id": rp_order["id"],
        "amount": amount_paise
    })

# ---------------- VERIFY PAYMENT ----------------
@order_bp.route("/api/payment/verify", methods=["POST"])
def verify_payment():
    data = request.json

    rp = razorpay_client()

    try:
        rp.utility.verify_payment_signature({
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": data["razorpay_payment_id"],
            "razorpay_signature": data["razorpay_signature"]
        })
    except:
        return jsonify({"success": False}), 400

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE orders
        SET
            razorpay_payment_id=%s,
            payment_status='PAID',
            status='CONFIRMED'
        WHERE razorpay_order_id=%s
    """, (
        data["razorpay_payment_id"],
        data["razorpay_order_id"]
    ))

    mysql.connection.commit()

    return jsonify({"success": True})

