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

    # Optimized Query: Handles cross-midnight pickups and strictly IST timezone
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
    WHERE f.is_active = 1 
    AND f.available_quantity > 0
    AND (
        -- Standard case: Start is before End (e.g. 18:00 to 22:00)
        (f.pickup_start <= f.pickup_end AND TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) BETWEEN f.pickup_start AND f.pickup_end)
        OR 
        -- Cross-midnight case: Start is after End (e.g. 22:00 to 02:00)
        (f.pickup_start > f.pickup_end AND (TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) >= f.pickup_start OR TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) <= f.pickup_end))
    )
    ORDER BY minutes_left ASC;
    """)

    rows = cur.fetchall()
    cur.close()

    foods = []
    for f in rows:
        rest_mrp = float(f["mrp"])
        rest_discounted = float(f["price"])
        
        # Calculate Platform Price: Discount + 15% (Rounded up for profit protection)
        platform_price = math.ceil(rest_discounted * 1.15)

        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": platform_price,  # Final price user pays
            "mrp": rest_mrp,         # Original restaurant price
            "available_quantity": f["available_quantity"],
            "restaurant_name": f["restaurant_name"],
            "minutes_left": max(0, int(f["minutes_left"]))
        })

    return jsonify({"foods": foods})
