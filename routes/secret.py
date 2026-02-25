from flask import Blueprint, jsonify
from utils.db import mysql
from MySQLdb.cursors import DictCursor

secret_bp = Blueprint("secret", __name__)


# ============================================================
# 1️⃣ GET RESTAURANTS THAT HAVE ACTIVE SECRET MENU TODAY
# ============================================================
@secret_bp.route("/api/secret-menu/restaurants", methods=["GET"])
def secret_restaurants():
    cur = mysql.connection.cursor(DictCursor)

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
        WHERE 
            sm.stock > 0
            AND (
                sm.is_today_special = 1
                OR DATE(CONVERT_TZ(sm.created_at, '+00:00', '+05:30')) = 
                   DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30'))
            )
        GROUP BY r.id
        ORDER BY r.name ASC
    """)

    items = cur.fetchall()

    return jsonify({
        "success": True,
        "restaurants": items
    })


# ============================================================
# 2️⃣ GET ALL SECRET DISHES OF ONE RESTAURANT (active today only)
# ============================================================
@secret_bp.route("/api/secret-menu/<int:rid>", methods=["GET"])
def secret_menu_by_restaurant(rid):
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT 
            sm.id,
            sm.name,
            sm.cuisine,
            sm.description,
            sm.price,
            sm.mrp,
            sm.stock,
            sm.img,
            r.name AS restaurant_name
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        WHERE 
            sm.restaurant_id = %s
            AND sm.stock > 0
            AND (
                sm.is_today_special = 1
                OR DATE(CONVERT_TZ(sm.created_at, '+00:00', '+05:30')) =
                   DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30'))
            )
        ORDER BY sm.id DESC
    """, (rid,))

    dishes = cur.fetchall()

    return jsonify({
        "success": True,
        "dishes": dishes
    })
