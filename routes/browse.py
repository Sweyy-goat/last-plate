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

        CASE
            WHEN f.pickup_end >= f.pickup_start THEN
                TIMESTAMPDIFF(
                    MINUTE,
                    TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')),
                    f.pickup_end
                )
            ELSE
                TIMESTAMPDIFF(
                    MINUTE,
                    TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')),
                    ADDTIME(f.pickup_end, '24:00:00')
                )
        END AS minutes_left

    FROM foods f
    JOIN restaurants r ON f.restaurant_id = r.id

    WHERE
        f.is_active = 1
        AND f.available_quantity > 0
        AND (
            (
                f.pickup_start <= f.pickup_end
                AND TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30'))
                    BETWEEN f.pickup_start AND f.pickup_end
            )
            OR
            (
                f.pickup_start > f.pickup_end
                AND (
                    TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) >= f.pickup_start
                    OR TIME(CONVERT_TZ(NOW(), '+00:00', '+05:30')) <= f.pickup_end
                )
            )
        )

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
