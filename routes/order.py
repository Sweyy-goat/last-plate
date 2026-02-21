from flask import Blueprint, render_template, request, jsonify, session, redirect
from utils.db import mysql
import MySQLdb.cursors
import math
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

    # 1. EXTRACT DATA FROM REQUEST (The fix for the NameError)
    data = request.json
    food_id = int(data["food_id"])
    quantity = int(data["quantity"])
    email = data["email"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Check stock and get price
    cur.execute("SELECT price, restaurant_id, available_quantity FROM foods WHERE id=%s FOR UPDATE", (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    # 2. MARKUP CALCULATION (Price + 15%)
    base_price = float(food["price"])
    platform_unit_price = math.ceil(base_price * 1.15) 
    total_amount_paise = platform_unit_price * quantity * 100

    # Create Razorpay Order
    razorpay_order = razorpay_client.order.create({
        "amount": total_amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    # Save PENDING order to DB
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
        platform_unit_price * quantity, 
        email,
        razorpay_order["id"]
    ))

    mysql.connection.commit()
    return jsonify({
        "razorpay_order_id": razorpay_order["id"],
        "amount": total_amount_paise,
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

    # Fetch order and restaurant details using 'mobile' column
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

    # 1. Stock Update
    cur.execute("""
        UPDATE foods 
        SET available_quantity = available_quantity - %s 
        WHERE id=%s AND available_quantity >= %s
    """, (order["quantity"], order["food_id"], order["quantity"]))

    if cur.rowcount == 0:
        mysql.connection.rollback()
        return jsonify({"success": False, "error": "Out of stock"}), 409

    # 2. GENERATE OTP
    otp = str(random.randint(100000, 999999))

    # 3. Update Order Table
    cur.execute("""
        UPDATE orders 
        SET payment_status='PAID', 
            status='CONFIRMED', 
            razorpay_payment_id=%s, 
            pickup_otp=%s 
        WHERE id=%s
    """, (data["razorpay_payment_id"], otp, order["id"]))

    mysql.connection.commit()

    # --- FINANCIAL REPORTING ---
    qty = order["quantity"]
    total_paid_by_user = float(order["total_amount"]) 
    res_unit_price = float(order["res_unit_price"])
    res_total_payout = res_unit_price * qty
    
    # 📧 Send OTP to User
    send_email(
        order["user_email"],
        "Your Last Plate Pickup OTP",
        f"<h2>Order Confirmed!</h2><p>Your OTP for <b>{order['food_name']}</b> is:</p><h1>{otp}</h1>"
    )

    # 📧 Send Detailed Info to Admin
    admin_body = f"""
    <h3>🚀 New Order Alert: {order['food_name']}</h3>
    <hr>
    <p><b>Revenue:</b><br>
    Collected from User: ₹{total_paid_by_user}<br>
    Pay to Restaurant: ₹{res_total_payout}<br>
    <b>Profit: ₹{total_paid_by_user - res_total_payout}</b></p>

    <p><b>Restaurant Details:</b><br>
    Name: {order['restaurant_name']}<br>
    GPay UPI: <code>{order['gpay_upi']}</code><br>
    Mobile: {order['res_mobile']}<br>
    OTP: <b>{otp}</b></p>
    """

    send_email("terminalplate@gmail.com", f"New Order: {order['food_name']}", admin_body)

    return jsonify({"success": True, "pickup_otp": otp})
