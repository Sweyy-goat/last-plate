from flask import Blueprint, request, jsonify, session
from utils.db import mysql
from datetime import datetime, timedelta

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

    try:
        # 🔐 START TRANSACTION
        cur.execute("START TRANSACTION")

        # 🔒 LOCK food row
        cur.execute("""
            SELECT
                id,
                restaurant_id,
                price,
                available_quantity,
                pickup_end
            FROM foods
            WHERE id = %s AND is_active = 1
            FOR UPDATE
        """, (food_id,))

        food = cur.fetchone()
        if not food:
            cur.execute("ROLLBACK")
            return jsonify({"error": "Food not found"}), 404

        # ⏰ FIX TIMEZONE (IST)
        cur.execute("""
            SELECT
                TIMESTAMP(
                    DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')),
                    %s
                ) > CONVERT_TZ(NOW(), '+00:00', '+05:30')
        """, (food["pickup_end"],))

        still_valid = cur.fetchone()[0]
        if not still_valid:
            cur.execute("ROLLBACK")
            return jsonify({"error": "Pickup window expired"}), 400

        # 📦 STOCK CHECK
        if food["available_quantity"] < quantity:
            cur.execute("ROLLBACK")
            return jsonify({"error": "Not enough quantity"}), 400

        total = food["price"] * quantity

        # ➖ REDUCE STOCK
        cur.execute("""
            UPDATE foods
            SET available_quantity = available_quantity - %s
            WHERE id = %s
        """, (quantity, food_id))

        # 📦 CREATE ORDER (VALID ENUM)
        cur.execute("""
            INSERT INTO orders
            (user_id, restaurant_id, total_amount, status)
            VALUES (%s, %s, %s, 'PAID')
        """, (
            session["user_id"],
            food["restaurant_id"],
            total
        ))

        order_id = cur.lastrowid

        # ✅ COMMIT
        mysql.connection.commit()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "amount": total
        })

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": "Server error", "details": str(e)}), 500
