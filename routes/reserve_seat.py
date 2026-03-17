from flask import Blueprint, render_template, request, jsonify
from app import limiter

reserve_seat_bp = Blueprint("reserve_seat", __name__)

@reserve_seat_bp.route("/reserve-seat")
def reserve_page():
    return render_template("restaurant/reserve_seat.html")

@reserve_seat_bp.route("/api/reserve-seat", methods=["POST"])
@limiter.limit("5 per minute")
def reserve():
    data = request.json
    return jsonify({"success": True})
