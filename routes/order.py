from flask import Blueprint, request, jsonify, session, redirect, render_template
from utils.db import mysql

order_bp = Blueprint("order", __name__)

# ---------- CHECKOUT PAGE ----------
@order_bp.route("/checkout/<int:food_id>")
def checkout_page(food_id):
    if session.get("role") != "user":
        return redirect("/login")

    return render_template("user/checkout.html", food_id=food_id)

# ---------- CREATE ORDER + LOCK QUANTITY ----------
@order_bp.route("/api/order/create", methods=["POST"])
def create_order():
    if session.get("role") != "user":
        return jsonify({"success": False}), 401

    data = request.json
    food_id = data["food_id"]
    qty = int(data["quantity"])
    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    # 🔒 ATOMIC QUANTITY LOCK
    cur.execute("""
        UPDATE foods
        SET available_quantity = available_quantity - %s
        WHERE id = %s AND available_quantity >= %s
    """, (qty, food_id, qty))

    if cur.rowcount == 0:
        return jsonify({"success": False, "message": "Not enough quantity"}), 400

    # Get food + restaurant info
    cur.execute("""
        SELECT restaurant_id, discount_price
        FROM foods WHERE id=%s
    """, (food_id,))
    food = cur.fetchone()

    restaurant_id = food[0]
    price = food[1]
    total = price * qty

    # Create order
    cur.execute("""
        INSERT INTO orders (user_id, restaurant_id, total_amount)
        VALUES (%s,%s,%s)
    """, (user_id, restaurant_id, total))
    order_id = cur.lastrowid

    # Add order item
    cur.execute("""
        INSERT INTO order_items (order_id, food_id, quantity)
        VALUES (%s,%s,%s)
    """, (order_id, food_id, qty))

    mysql.connection.commit()

    return jsonify({
        "success": True,
        "order_id": order_id,
        "amount": total
    })
