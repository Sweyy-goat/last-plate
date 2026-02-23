from flask import Blueprint, jsonify, session, render_template
from utils.db import mysql
import MySQLdb.cursors

savings_bp = Blueprint("savings", __name__)

# -------------------------------
# PAGE ROUTE  ( /savings )
# -------------------------------
@savings_bp.route('/savings')
def savings_page():
    return render_template('user/savings.html')


# -------------------------------
# API ROUTE  ( /api/savings )
# -------------------------------
@savings_bp.route('/api/savings', methods=['GET'])
def get_savings():
    user_id = session.get('user_id', 1)

    conn = mysql.connection
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # -----------------------------------
    # 1. TOTAL MEALS + TOTAL SAVINGS
    # -----------------------------------
    query_total = """
        SELECT 
            COUNT(o.id) AS meals_rescued,
            COALESCE(SUM((f.original_price - f.price) * o.quantity), 0) AS total_saved
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        WHERE o.user_id = %s
        AND o.status IN ('CONFIRMED', 'PICKED_UP')
        AND o.payment_status = 'PAID'
    """
    cur.execute(query_total, (user_id,))
    total_stats = cur.fetchone()

    # -----------------------------------
    # 2. TODAY SAVINGS
    # -----------------------------------
    query_today = """
        SELECT 
            COALESCE(SUM((f.original_price - f.price) * o.quantity), 0) AS saved_today
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        WHERE o.user_id = %s
        AND o.status IN ('CONFIRMED', 'PICKED_UP')
        AND o.payment_status = 'PAID'
        AND DATE(o.created_at) = CURDATE()
    """
    cur.execute(query_today, (user_id,))
    today_stats = cur.fetchone()

    # -----------------------------------
    # 3. RECENT TRANSACTIONS
    # -----------------------------------
    query_tx = """
        SELECT 
            r.name AS restaurant_name,
            o.created_at,
            (f.original_price - f.price) * o.quantity AS amount_saved
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        JOIN restaurants r ON o.restaurant_id = r.id
        WHERE o.user_id = %s
        AND o.status = 'PICKED_UP'
        ORDER BY o.created_at DESC
        LIMIT 5
    """
    cur.execute(query_tx, (user_id,))
    recent_orders = cur.fetchall()

    # Format data
    total_saved = int(total_stats["total_saved"])
    saved_today = int(today_stats["saved_today"])
    meals = total_stats["meals_rescued"]

    formatted_tx = []
    for tx in recent_orders:
        formatted_tx.append({
            "icon": "🥗",
            "type": "credit",
            "name": f"Rescued from {tx['restaurant_name']}",
            "place": tx['restaurant_name'],
            "time": tx['created_at'].strftime("%b %d, %I:%M %p"),
            "amount": f"+₹{int(tx['amount_saved'])}"
        })

    return jsonify({
        "total_saved": total_saved,
        "saved_today": saved_today,
        "meals_rescued": meals,
        "food_kg": round(meals * 0.4, 1),
        "co2_kg": round(meals * 1.2, 1),
        "streak": 3,
        "city_rank": 47,
        "referral_code": "RESCUE50",
        "week_days": [
            {"day": "Mon", "done": True},
            {"day": "Tue", "done": True},
            {"day": "Wed", "done": True},
            {"day": "Thu", "done": False},
            {"day": "Fri", "done": False},
            {"day": "Sat", "done": False},
            {"day": "Sun", "done": False, "today": True}
        ],
        "milestones": [
            {"icon": "🥗", "name": "First Rescue", "desc": "Complete your first rescue", "reward": "Unlocked", "progress": 100, "unlocked": meals > 0},
            {"icon": "🌍", "name": "10 Meals Rescued", "desc": "Rescue 10 meals total", "reward": "₹75 Off", "progress": min(meals/10*100, 100), "unlocked": meals >= 10}
        ],
        "transactions": formatted_tx
    })
