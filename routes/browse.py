from flask import Blueprint, render_template, session, redirect, jsonify
from utils.db import mysql
import MySQLdb.cursors
import math

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

    # We use %s to pass the current IST time to avoid MySQL timezone table errors
    from datetime import datetime, timedelta
    # India is UTC + 5.5 hours
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time_ist = ist_now.strftime('%H:%M:%S')

    cur.execute("""
    SELECT 
        f.id, f.name, f.price, f.mrp, f.available_quantity, 
        f.pickup_start, f.pickup_end, r.name AS restaurant_name,
        CASE 
            WHEN f.pickup_end >= f.pickup_start THEN 
                TIMESTAMPDIFF(MINUTE, %s, f.pickup_end)
            ELSE 
                TIMESTAMPDIFF(MINUTE, %s, ADDTIME(f.pickup_end, '24:00:00'))
        END AS minutes_left
    FROM foods f
    JOIN restaurants r ON f.restaurant_id = r.id
    WHERE f.is_active = 1 
    AND f.available_quantity > 0
    AND (
        (f.pickup_start <= f.pickup_end AND %s BETWEEN f.pickup_start AND f.pickup_end)
        OR 
        (f.pickup_start > f.pickup_end AND (%s >= f.pickup_start OR %s <= f.pickup_end))
    )
    ORDER BY minutes_left ASC;
    """, (current_time_ist, current_time_ist, current_time_ist, current_time_ist, current_time_ist))

    rows = cur.fetchall()
    cur.close()

    foods = []
    for f in rows:
        restaurant_original_mrp = float(f["mrp"])
        restaurant_discount_price = float(f["price"])
        
        # 15% Platform Markup
        final_platform_price = math.ceil(restaurant_discount_price * 1.15)

        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": final_platform_price,
            "mrp": restaurant_original_mrp,
            "available_quantity": f["available_quantity"],
            "restaurant_name": f["restaurant_name"],
            "minutes_left": max(0, int(f["minutes_left"]))
        })

    return jsonify({"foods": foods})
