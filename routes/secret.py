from flask import Blueprint, jsonify
from utils.db import mysql

secret_bp = Blueprint("secret", __name__)

@secret_bp.route("/api/secret-menu", methods=["GET"])
def secret_menu():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT sm.*, r.name AS restaurant_name
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        ORDER BY sm.is_today_special DESC, sm.id DESC
    """)
    
    items = cur.fetchall()

    return jsonify({"success": True, "items": items})
