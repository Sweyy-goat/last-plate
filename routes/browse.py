from flask import Blueprint, render_template, session, redirect, jsonify
from utils.db import mysql
import MySQLdb.cursors
import math # Add this at the top of your file

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

    cur.execute("""
    SELECT 
        f.id, f.name, f.price, f.mrp, f.available_quantity, 
        f.pickup_start, f.pickup_end, r.name AS restaurant_name,
        CASE 
            WHEN f.pickup_end >= f.pickup_start THEN 
                TIMESTAMPDIFF(MINUTE, TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')), f.pickup_end)
            ELSE 
                TIMESTAMPDIFF(MINUTE, TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')), ADDTIME(f.pickup_end, '24:00:00'))
        END AS minutes_left
    FROM foods f
    JOIN restaurants r ON f.restaurant_id = r.id
    WHERE f.is_active = 1 AND f.available_quantity > 0
    AND (
        (f.pickup_start <= f.pickup_end AND TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) BETWEEN f.pickup_start AND f.pickup_end)
        OR 
        (f.pickup_start > f.pickup_end AND (TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) >= f.pickup_start OR TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) <= f.pickup_end))
    )
    ORDER BY minutes_left ASC;
    """)

    rows = cur.fetchall()
    cur.close()

    foods = []
    for f in rows:
        # RAW DATA FROM DB
        restaurant_original_mrp = float(f["mrp"])
        restaurant_discount_price = float(f["price"])
        
        # APPLY 15% MARKUP (Your Profit Margin)
        # Using math.ceil ensures you always round up to the next Rupee
        final_platform_price = math.ceil(restaurant_discount_price * 1.15)

        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": final_platform_price,  # This is what the user pays (Incl. your 15%)
            "mrp": restaurant_original_mrp, # This is the real strikethrough price
            "available_quantity": f["available_quantity"],
            "restaurant_name": f["restaurant_name"],
            "minutes_left": max(0, int(f["minutes_left"]))
        })

    return jsonify({"foods": foods})
