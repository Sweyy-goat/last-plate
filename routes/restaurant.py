from flask import Blueprint, render_template, request, jsonify, session, redirect
from utils.db import mysql

restaurant_bp = Blueprint("restaurant", __name__, url_prefix="/restaurant")

# ----------- AUTH GUARD -----------
def restaurant_required():
    return session.get("role") == "restaurant"


# ----------- DASHBOARD PAGE -----------
@restaurant_bp.route("/dashboard")
def dashboard():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/dashboard.html")


# ----------- ADD FOOD PAGE -----------
@restaurant_bp.route("/add-food")
def add_food_page():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/add_food.html")


# ----------- ADD FOOD API -----------
@restaurant_bp.route("/api/add-food", methods=["POST"])
def add_food():
    if not restaurant_required():
        return jsonify({"success": False}), 401

    data = request.json
    restaurant_id = session["restaurant_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO foods
        (restaurant_id, name, original_price, price,
         available_quantity, pickup_start, pickup_end, is_active)
        VALUES (%s,%s,%s,%s,%s,%s,%s,1)
    """, (
        restaurant_id,
        data["name"],
        data["original_price"],
        data["price"],
        data["quantity"],
        data["pickup_start"],
        data["pickup_end"]
    ))
    mysql.connection.commit()

    return jsonify({"success": True})


# ----------- VIEW MY FOODS API -----------
@restaurant_bp.route("/api/my-foods")
def my_foods():
    if not restaurant_required():
        return jsonify([]), 401

    restaurant_id = session["restaurant_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT
            id,
            name,
            price,
            available_quantity,
            pickup_start,
            pickup_end,
            is_active
        FROM foods
        WHERE restaurant_id = %s
        ORDER BY pickup_end ASC
    """, (restaurant_id,))

    rows = cur.fetchall()

    foods = []
    for f in rows:
        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": f["price"],
            "available_quantity": f["available_quantity"],
            "pickup_start": str(f["pickup_start"]),
            "pickup_end": str(f["pickup_end"]),
            "is_active": f["is_active"],
        })

    return jsonify(foods)


# ----------- CANCEL FOOD (FORCE HIDE) -----------
@restaurant_bp.route("/api/cancel-food/<int:food_id>", methods=["POST"])
def cancel_food(food_id):
    if not restaurant_required():
        return jsonify({"success": False}), 401

    restaurant_id = session["restaurant_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE foods
        SET is_active = 0
        WHERE id = %s AND restaurant_id = %s
    """, (food_id, restaurant_id))

    mysql.connection.commit()
    return jsonify({"success": True})


# ----------- UPDATE FOOD QUANTITY / SOLD OUT -----------
@restaurant_bp.route("/api/update-food-quantity/<int:food_id>", methods=["POST"])
def update_food_quantity(food_id):
    if not restaurant_required():
        return jsonify({"success": False}), 401

    data = request.json
    new_qty = int(data["quantity"])
    restaurant_id = session["restaurant_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE foods
        SET
            available_quantity = %s,
            is_active = IF(%s > 0, 1, 0)
        WHERE id = %s AND restaurant_id = %s
    """, (new_qty, new_qty, food_id, restaurant_id))

    mysql.connection.commit()
    return jsonify({"success": True})
