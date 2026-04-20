from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from utils.db import mysql, set_mysql_timezone

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from flask_jwt_extended import JWTManager


app = Flask(__name__)

# Config
app.config.from_pyfile("config.py")
app.secret_key = app.config["SECRET_KEY"]

CORS(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

app.config["JWT_SECRET_KEY"] = app.config["SECRET_KEY"]
jwt = JWTManager(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"]
)

mysql.init_app(app)

with app.app_context():
    try:
        set_mysql_timezone()
    except Exception as e:
        print("Timezone init skipped:", e)


# ================= BLUEPRINTS =================

from routes.auth import auth_bp
from routes.cities import cities_bp
from routes.reserve_seat import reserve_seat_bp
from routes.restaurant import restaurant_bp
from routes.browse import browse_bp
from routes.order import order_bp
from routes.savings import savings_bp
from routes.secret import secret_bp


# ✅ FIX: Register blueprints ONCE only.
# The routes inside each blueprint already include /api/ where needed,
# so adding url_prefix="/api" again would double it → /api/api/foods (broken)
app.register_blueprint(auth_bp)
app.register_blueprint(cities_bp)
app.register_blueprint(reserve_seat_bp)
app.register_blueprint(restaurant_bp)
app.register_blueprint(browse_bp)
app.register_blueprint(order_bp)
app.register_blueprint(savings_bp)
app.register_blueprint(secret_bp)


# ================= WEBSITE ROUTES =================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/how")
def how():
    return render_template("how.html")


# ================= ERROR HANDLING =================

@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith("/api"):
        return jsonify({
            "status": "error",
            "message": "Too many requests"
        }), 429

    return render_template("429.html"), 429


# ================= MAIN =================

if __name__ == "__main__":
    app.run(debug=True)
