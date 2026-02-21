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


# ================= CHECKOUT =================
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

    if not food or food["available_quantity"] <= 0:
        return "Food unavailable", 404

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

    # In create_order route
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
# ================= VERIFY PAYMENT =================
@order_bp.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        razorpay_client.utility.verify_payment_signature(data)
    except:
        return jsonify({"success": False}), 400

    # FIX: Changed r.phone to r.mobile to match your database schema
    cur.execute("""
        SELECT o.*, f.name AS food_name, f.price AS res_unit_price, 
               r.name AS restaurant_name, r.gpay_upi, r.mobile AS res_mobile
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        JOIN restaurants r ON f.restaurant_id = r.id
        WHERE o.razorpay_order_id=%s AND o.payment_status='PENDING'
        FOR UPDATE
    """, (data["razorpay_order_id"],))
    order = cur.fetchone()

    if not order:
        return jsonify({"success": False}), 400

    # ... [Keep your existing stock update and order status update code here] ...

    # --- MATH FOR ADMIN EMAIL ---
    qty = order["quantity"]
    res_unit_price = float(order["res_unit_price"])
    res_total_payout = res_unit_price * qty
    
    platform_unit_price = math.ceil(res_unit_price * 1.15)
    platform_total_collected = platform_unit_price * qty

    # 📧 Send OTP to User
    send_email(
        order["user_email"],
        "Your Last Plate Pickup OTP",
        f"<h2>Order Confirmed!</h2><p>Your OTP for <b>{order['food_name']}</b> is:</p><h1>{otp}</h1>"
    )

    # 📧 Send Detailed Info to Admin
    admin_email_body = f"""
    <h3>🚀 New Order for {order['restaurant_name']}</h3>
    <hr>
    <p><b>Order Details:</b><br>
    Item: {order['food_name']} (ID: {order['food_id']})<br>
    Quantity: {qty}<br>
    OTP: <b>{otp}</b></p>

    <p><b>Financial Breakdown:</b><br>
    Restaurant Rate: ₹{res_unit_price}<br>
    Platform Rate (User Paid): ₹{platform_unit_price}<br>
    <b>Total Collected: ₹{platform_total_collected}</b></p>

    <p><b>Payout Information:</b><br>
    Restaurant: {order['restaurant_name']}<br>
    GPay UPI: <code>{order['gpay_upi']}</code><br>
    Mobile: {order['res_mobile']}<br>
    <b>Amount to Transfer: ₹{res_total_payout}</b></p>
    """

    send_email(
        "sidharthsunil1305@gmail.com",
        f"Order Alert: {order['food_name']} ({order['restaurant_name']})",
        admin_email_body
    )

    return jsonify({"success": True, "pickup_otp": otp})
