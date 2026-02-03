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

    query = """
    SELECT 
        f.id, f.name, f.price, f.mrp, f.available_quantity,
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
        raw_mrp = float(f["mrp"])
        restaurant_discount = float(f["price"])
        valid_mrp = raw_mrp if raw_mrp > 0 else restaurant_discount

        platform_price = math.ceil(restaurant_discount * 1.15)
        display_mrp = valid_mrp if valid_mrp > platform_price else math.ceil(platform_price * 1.2)

        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": platform_price,
            "mrp": display_mrp,
            "available_quantity": f["available_quantity"],
            "restaurant_name": f["restaurant_name"],
            "restaurant_address": f["restaurant_address"],
            "minutes_left": max(0, int(f["minutes_left"]))
        })

    return jsonify({"foods": foods})

