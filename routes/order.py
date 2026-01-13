from flask import Blueprint, render_template, request, jsonify, session, redirect
from utils.db import mysql
import MySQLdb.cursors
import razorpay, os, random
from utils.emailer import send_email

order_bp = Blueprint("order", __name__)

razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))


# ================= CHECKOUT PAGE =================
@order_bp.route("/checkout/<int:food_id>")
def checkout(food_id):
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT f.id, f.name, f.price, f.available_quantity,
               r.name AS restaurant_name
        FROM foods f
        JOIN restaurants r ON f.restaurant_id = r.id
        WHERE f.id=%s AND f.is_active=1
    """, (food_id,))
    food = cur.fetchone()

    if not food:
        return "Food not found", 404

    return render_template("checkout.html", food=food)


# ================= CREATE ORDER =================
@order_bp.route("/api/create-order", methods=["POST"])
def create_order():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    food_id = int(data["food_id"])
    quantity = int(data["quantity"])
    email = data["email"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT price, restaurant_id, available_quantity
        FROM foods WHERE id=%s FOR UPDATE
    """, (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    amount = food["price"] * quantity * 100

    razorpay_order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    cur.execute("""
        INSERT INTO orders
        (user_id, food_id, quantity, restaurant_id,
         total_amount, user_email, status, payment_status, razorpay_order_id)
        VALUES (%s,%s,%s,%s,%s,%s,'PENDING','PENDING',%s)
    """, (
        session["user_id"],
        food_id,
        quantity,
        food["restaurant_id"],
        amount / 100,
        email,
        razorpay_order["id"]
    ))

    mysql.connection.commit()

    return jsonify({
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount,
        "key": os.getenv("RAZORPAY_KEY_ID")
    })


# ================= VERIFY PAYMENT =================
@order_bp.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        razorpay_client.utility.verify_payment_signature(data)
    except:
        return jsonify({"success": False}), 400

    cur.execute("""
        SELECT * FROM orders
        WHERE razorpay_order_id=%s AND payment_status='PENDING'
        FOR UPDATE
    """, (data["razorpay_order_id"],))
    order = cur.fetchone()

    if not order:
        return jsonify({"success": False}), 400

    cur.execute("""
        UPDATE foods
        SET available_quantity = available_quantity - %s
        WHERE id=%s AND available_quantity >= %s
    """, (order["quantity"], order["food_id"], order["quantity"]))

    if cur.rowcount == 0:
        mysql.connection.rollback()
        return jsonify({"success": False}), 409

    otp = str(random.randint(100000, 999999))

    cur.execute("""
        UPDATE orders
        SET payment_status='PAID',
            status='CONFIRMED',
            razorpay_payment_id=%s,
            pickup_otp=%s
        WHERE id=%s
    """, (data["razorpay_payment_id"], otp, order["id"]))

    mysql.connection.commit()

    send_email(
        order["user_email"],
        "Your Last Plate Pickup OTP",
        f"<h2>Your Pickup OTP</h2><h1>{otp}</h1>"
    )

    return jsonify({"success": True, "pickup_otp": otp})
