from flask import Blueprint, render_template, request, jsonify
from app import limiter

reservation_bp = Blueprint("reservation", __name__)

@reservation_bp.route("/reserve-seat")
def reserve_page():
    return render_template("reserve-seat.html")

@reservation_bp.route("/api/reserve-seat", methods=["POST"])
@limiter.limit("5 per minute")
def reserve():
    data = request.json
    return jsonify({"success": True})
