from flask import Blueprint, render_template, session, redirect, jsonify
from utils.db import mysql

browse_bp = Blueprint("browse", __name__)

# -------- ENTRY POINT FOR BROWSE BUTTON --------
@browse_bp.route("/browse-entry")
def browse_entry():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "user":
        return redirect("/")

    return redirect("/browse")

# -------- ACTUAL BROWSE PAGE --------
@browse_bp.route("/browse")
def browse_page():
    if "user_id" not in session or session.get("role") != "user":
        return redirect("/login")

    return render_template("user/browse.html")

# -------- FOOD LIST API --------
@browse_bp.route("/api/foods")
def food_list():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            f.id,
            f.name,
            f.price,
            f.available_quantity,
            f.pickup_start,
            f.pickup_end,
            r.name
        FROM foods f
        JOIN restaurants r ON f.restaurant_id = r.id
        WHERE
            f.available_quantity > 0
            AND f.is_active = 1
            AND CURTIME() <= f.pickup_end
    """)

    rows = cur.fetchall()

    foods = []
    for f in rows:
        foods.append({
            "id": f[0],
            "name": f[1],
            "price": f[2],
            "available_quantity": f[3],
            "pickup_start": str(f[4]),
            "pickup_end": str(f[5]),
            "restaurant_name": f[6]
        })

    return jsonify({"foods": foods})
