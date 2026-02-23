from flask import Blueprint, jsonify
from utils.db import mysql

secret_bp = Blueprint("secret", __name__)

# ----------------------------------------------
# GET RESTAURANTS THAT HAVE SECRET MENU DISHES
# ----------------------------------------------
@secret_bp.route("/api/secret-menu/restaurants", methods=["GET"])
def secret_restaurants():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT 
            r.id AS restaurant_id,
            r.name AS restaurant_name,
            r.address,
            COUNT(sm.id) AS dish_count,
            MIN(sm.price) AS min_price,
            MAX(sm.price) AS max_price
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        GROUP BY r.id
        ORDER BY r.name ASC
    """)

    items = cur.fetchall()

    return jsonify({
        "success": True,
        "restaurants": items
    })
