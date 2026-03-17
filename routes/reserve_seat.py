from flask import Blueprint, render_template, request, jsonify
from app import limiter
from utils.db import mysql
import MySQLdb.cursors

reserve_seat_bp = Blueprint("reserve_seat", __name__)

@reserve_seat_bp.route("/reserve-seat", strict_slashes=False)
def reserve_page():
    return render_template("restaurant/reserve_seat.html")

@reserve_seat_bp.route("/api/reserve-seat", methods=["POST"])
@limiter.limit("5 per minute")
def reserve():
    data = request.get_json()
    print("DATA RECEIVED:", data)

    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    date = data.get("date")
    time = data.get("time")
    guests = data.get("guests")
    occasion = data.get("occasion")
    notes = data.get("notes")

    print(name, email, phone, date, time, guests)

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO reservations
        (name, email, phone, reservation_date, reservation_time, guests, occasion, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        name, email, phone, date, time, guests, occasion, notes
    ))

    mysql.connection.commit()

    return jsonify({"success": True})
