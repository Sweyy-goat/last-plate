# browse.py
from flask import Blueprint, render_template, session, redirect, jsonify
from utils.db import mysql
import MySQLdb.cursors
import math
from datetime import datetime, timedelta

browse_bp = Blueprint("browse", __name__)

@browse_bp.route("/browse-entry")
def browse_entry():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") != "user":
        return redirect("/")
    return redirect("/browse")

@browse_bp.route("/browse")
def browse_page():
    if "user_id" not in session or session.get("role") != "user":
        return redirect("/login")
    return render_template("user/browse.html")

@browse_bp.route("/api/foods")
def food_list():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Convert UTC → IST
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time_ist = ist_now.strftime('%H:%M:%S')

    # UPDATED QUERY: Added f.original_price to the SELECT list
    query = """
    SELECT 
        f.id, f.name, f.original_price, f.price, f.available_quantity,
        f.pickup_start, f.pickup_end,
        r.name AS restaurant_name,
        r.address AS restaurant_address,
        CASE
            WHEN f.pickup_end >= f.pickup_start THEN 
                TIMESTAMPDIFF(MINUTE, CAST(%s AS TIME), f.pickup_end)
            ELSE
                TIMESTAMPDIFF(MINUTE, CAST(%s AS TIME), ADDTIME(f.pickup_end, '24:00:00'))
        END AS minutes_left
    FROM foods f
    JOIN restaurants r ON f.restaurant_id = r.id
    WHERE f.is_active = 1
      AND f.available_quantity > 0
      AND (
          (f.pickup_start <= f.pickup_end AND CAST(%s AS TIME) BETWEEN f.pickup_start AND f.pickup_end)
          OR
          (f.pickup_start > f.pickup_end AND 
                (CAST(%s AS TIME) >= f.pickup_start OR CAST(%s AS TIME) <= f.pickup_end)
          )
      )
    ORDER BY minutes_left ASC;
    """

    cur.execute(query, (
        current_time_ist,
        current_time_ist,
        current_time_ist,
        current_time_ist,
        current_time_ist
    ))

    rows = cur.fetchall()
    cur.close()

    foods = []
    for f in rows:
        # The price set by the restaurant in the dashboard
        restaurant_discounted_price = float(f["price"])
        
        # Original price from DB (e.g., 200)
        # Fallback to restaurant_price if original_price is missing or 0
        raw_original = float(f["original_price"]) if f.get("original_price") and f["original_price"] > 0 else restaurant_discounted_price

        # Your Platform Selling Price (The price user sees and pays: 180 * 1.15 = 207)
        platform_selling_price = math.ceil(restaurant_discounted_price * 1.15)

        # Final Display MRP (The strike-through: 200 * 1.15 = 230)
        # We apply the same 15% to the original price so the discount ratio stays consistent
        display_mrp = math.ceil(raw_original * 1.15)

        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": platform_selling_price, # Actual Price
            "mrp": display_mrp,              # Strike-through Price
            "available_quantity": f["available_quantity"],
            "restaurant_name": f["restaurant_name"],
            "restaurant_address": f["restaurant_address"],
            "minutes_left": max(0, int(f["minutes_left"]))
        })

    return jsonify({"foods": foods})
