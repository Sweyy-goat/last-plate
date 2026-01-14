from flask import Blueprint, render_template, session, redirect, jsonify
from utils.db import mysql
import MySQLdb.cursors

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
            f.id,
            f.name,
            f.price,
            f.available_quantity,
            f.pickup_start,
            f.pickup_end,
            r.name AS restaurant_name,

            TIMESTAMPDIFF(
                MINUTE,
                CONVERT_TZ(NOW(), '+00:00', '+05:30'),
                TIMESTAMP(
                    DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')),
                    f.pickup_end
                )
            ) AS minutes_left

        FROM foods f
        JOIN restaurants r ON f.restaurant_id = r.id

        WHERE
            f.is_active = 1
            AND f.available_quantity > 0
            AND TIMESTAMP(
                DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')),
                f.pickup_end
            ) > CONVERT_TZ(NOW(), '+00:00', '+05:30')

        ORDER BY minutes_left ASC;
    """)

    rows = cur.fetchall()
    cur.close()

    foods = [{
        "id": f["id"],
        "name": f["name"],
        "price": f["price"],
        "available_quantity": f["available_quantity"],
        "pickup_start": str(f["pickup_start"]),
        "pickup_end": str(f["pickup_end"]),
        "restaurant_name": f["restaurant_name"],
        "minutes_left": max(0, int(f["minutes_left"]))
    } for f in rows]

    return jsonify({"foods": foods})
