from flask import Blueprint, request, jsonify, session
from utils.db import mysql
from datetime import datetime

order_bp = Blueprint("order", __name__)

@order_bp.route("/api/reserve", methods=["POST"])
def reserve_food():
    if "user_id" not in session or session.get("role") != "user":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    food_id = data.get("food_id")
    quantity = int(data.get("quantity", 1))

    if quantity <= 0:
        return jsonify({"error": "Invalid quantity"}), 400

    cur = mysql.connection.cursor()

    # 🔒 LOCK food row (IMPORTANT)
    cur.execute("""
        SELECT id, restaurant_id, price, available_quantity, pickup_end
        FROM foods
        WHERE id=%s
        FOR UPDATE
    """, (food_id,))

    food = cur.fetchone()
    if not food:
        return jsonify({"error": "Food not found"}), 404

    # ⏰ pickup expired
    if food["pickup_end"] <= datetime.now().time():
        return jsonify({"error": "Pickup window expired"}), 400

    if food["available_quantity"] < quantity:
        return jsonify({"error": "Not enough quantity"}), 400

    total = food["price"] * quantity

    # ➖ Reduce quantity
    cur.execute("""
        UPDATE foods
        SET available_quantity = available_quantity - %s
        WHERE id=%s
    """, (quantity, food_id))

    # 📦 Create order
    cur.execute("""
        INSERT INTO orders
        (user_id, restaurant_id, total_amount, status, payment_status)
        VALUES (%s,%s,%s,'PENDING','PENDING')
    """, (
        session["user_id"],
        food["restaurant_id"],
        total
    ))

    order_id = cur.lastrowid
    mysql.connection.commit()

    return jsonify({
        "success": True,
        "order_id": order_id,
        "amount": total
    })
