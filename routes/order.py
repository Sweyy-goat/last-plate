from flask import Blueprint, render_template, session, redirect
from utils.db import mysql
import MySQLdb.cursors

order_bp = Blueprint("order", __name__)

@order_bp.route("/checkout/<int:food_id>")
def checkout(food_id):
    if "user_id" not in session or session.get("role") != "user":
        return redirect("/login")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT id, name, price, available_quantity
        FROM foods
        WHERE id = %s AND is_active = 1
    """, (food_id,))

    food = cur.fetchone()

    if not food:
        return "Food not found", 404

    return render_template(
        "checkout.html",
        food_id=food["id"],
        food_name=food["name"],
        price=food["price"],
        max_qty=food["available_quantity"]
    )
