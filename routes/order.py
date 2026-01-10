from flask import Blueprint, render_template, request, jsonify, session, redirect
from utils.db import mysql
import MySQLdb.cursors
from datetime import datetime, time

order_bp = Blueprint("order", __name__)

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
            f.pickup_end,
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


# ---------------- CREATE ORDER (PENDING) ----------------
@order_bp.route("/api/reserve", methods=["POST"])
def reserve_food():
    if "user_id" not in session or session.get("role") != "user":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json
    food_id = int(data.get("food_id"))
    quantity = int(data.get("quantity"))

    if quantity <= 0:
        return jsonify({"success": False, "message": "Invalid quantity"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 🔒 LOCK FOOD ROW
    cur.execute("""
        SELECT id, restaurant_id, price, available_quantity, pickup_end
        FROM foods
        WHERE id = %s
        FOR UPDATE
    """, (food_id,))

    food = cur.fetchone()

    if not food:
        return jsonify({"success": False, "message": "Food not found"}), 404

    if food["available_quantity"] < quantity:
        return jsonify({"success": False, "message": "Not enough quantity"}), 400

    # ⏰ pickup expired safety
    if food["pickup_end"] <= datetime.now().time():
        return jsonify({"success": False, "message": "Pickup window expired"}), 400

    total_amount = food["price"] * quantity

    # ➖ reduce stock
    cur.execute("""
        UPDATE foods
        SET available_quantity = available_quantity - %s
        WHERE id = %s
    """, (quantity, food_id))

    # 📦 create order (PENDING)
    cur.execute("""
        INSERT INTO orders
        (user_id, restaurant_id, total_amount, status, payment_status, created_at)
        VALUES (%s, %s, %s, 'PENDING', 'PENDING', NOW())
    """, (
        session["user_id"],
        food["restaurant_id"],
        total_amount
    ))

    order_id = cur.lastrowid
    mysql.connection.commit()

    return jsonify({
        "success": True,
        "order_id": order_id,
        "amount": total_amount
    })


# ---------------- CONFIRM RESERVATION ----------------
@order_bp.route("/api/order/confirm", methods=["POST"])
def confirm_order():
    if "user_id" not in session or session.get("role") != "user":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json
    order_id = data.get("order_id")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 🔎 check ownership & status
    cur.execute("""
        SELECT id, status
        FROM orders
        WHERE id = %s AND user_id = %s
    """, (order_id, session["user_id"]))

    order = cur.fetchone()

    if not order:
        return jsonify({"success": False, "message": "Order not found"}), 404

    if order["status"] != "PENDING":
        return jsonify({"success": False, "message": "Order already processed"}), 400

    # ✅ CONFIRM ORDER
    cur.execute("""
        UPDATE orders
        SET status = 'CONFIRMED'
        WHERE id = %s
    """, (order_id,))

    mysql.connection.commit()

    return jsonify({
        "success": True,
        "message": "Reservation confirmed"
    })
