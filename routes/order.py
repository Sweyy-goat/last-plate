from flask import Blueprint, render_template, request, jsonify, session, redirect, current_app
from utils.db import mysql
import MySQLdb.cursors
import razorpay
import os

order_bp = Blueprint("order", __name__)

# Razorpay client
razorpay_client = razorpay.Client(auth=(
    os.getenv("rzp_test_S2bmctosdabOoM"),
    os.getenv("77RfmWU2bJoKhsAknuxti9bi")
))


# ---------------- CHECKOUT PAGE ----------------
@order_bp.route("/checkout/<int:food_id>")
def checkout(food_id):
    if "user_id" not in session or session.get("role") != "user":
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


# ---------------- CREATE RAZORPAY ORDER ----------------
@order_bp.route("/api/create-order", methods=["POST"])
def create_order():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    food_id = int(data["food_id"])
    quantity = int(data["quantity"])

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT id, restaurant_id, price, available_quantity
        FROM foods
        WHERE id=%s
        FOR UPDATE
    """, (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] < quantity:
        return jsonify({"error": "Not available"}), 400

    amount = food["price"] * quantity * 100  # paise

    # Create Razorpay order
    razorpay_order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    # Save order
    cur.execute("""
        INSERT INTO orders
        (user_id, restaurant_id, total_amount, status, payment_status, razorpay_order_id)
        VALUES (%s,%s,%s,'PENDING','PENDING',%s)
    """, (
        session["user_id"],
        food["restaurant_id"],
        amount / 100,
        razorpay_order["id"]
    ))

    mysql.connection.commit()

    return jsonify({
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount,
        "key": os.getenv("RAZORPAY_KEY_ID")
    })


# ---------------- VERIFY PAYMENT ----------------
@order_bp.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json

    razorpay_payment_id = data["razorpay_payment_id"]
    razorpay_order_id = data["razorpay_order_id"]
    razorpay_signature = data["razorpay_signature"]

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_signature": razorpay_signature
        })
    except:
        return jsonify({"success": False}), 400

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE orders
        SET payment_status='PAID', razorpay_payment_id=%s
        WHERE razorpay_order_id=%s
    """, (razorpay_payment_id, razorpay_order_id))

    mysql.connection.commit()

    return jsonify({"success": True})


