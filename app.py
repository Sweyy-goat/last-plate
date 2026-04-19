from flask import Flask, jsonify, render_template
from flask_cors import CORS

from utils.db import mysql, set_mysql_timezone

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from flask_jwt_extended import JWTManager


app = Flask(__name__)

# 🔥 Config
app.config.from_pyfile("config.py")
app.secret_key = app.config["SECRET_KEY"]

# 🔥 Proxy fix (Railway / deployment)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# 🔥 Enable CORS (ONLY needed for API)
CORS(app)

# 🔥 JWT
app.config["JWT_SECRET_KEY"] = app.config["SECRET_KEY"]
jwt = JWTManager(app)

# 🔥 Rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"]
)

# 🔥 MySQL
mysql.init_app(app)

# 🔥 DB init
with app.app_context():
    try:
        set_mysql_timezone()
    except Exception as e:
        print("Timezone init skipped:", e)


# ================= BLUEPRINTS =================

# 👉 Auth (SPECIAL CASE: contains BOTH web + API routes)
from routes.auth import auth_bp
app.register_blueprint(auth_bp)   # ❗ NO prefix here


# 👉 PURE API routes (safe to prefix)
from routes.cities import cities_bp
from routes.reserve_seat import reserve_seat_bp
from routes.restaurant import restaurant_bp
from routes.browse import browse_bp
from routes.order import order_bp
from routes.savings import savings_bp
from routes.secret import secret_bp

app.register_blueprint(cities_bp, url_prefix="/api")
app.register_blueprint(reserve_seat_bp, url_prefix="/api")
app.register_blueprint(restaurant_bp, url_prefix="/api")
app.register_blueprint(browse_bp, url_prefix="/api")
app.register_blueprint(order_bp, url_prefix="/api")
app.register_blueprint(savings_bp, url_prefix="/api")
app.register_blueprint(secret_bp, url_prefix="/api")


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
    # API → JSON
    if request.path.startswith("/api"):
        return jsonify({
            "status": "error",
            "message": "Too many requests"
        }), 429

    # Website → HTML
    return render_template("429.html"), 429


# ================= MAIN =================

if __name__ == "__main__":
    app.run(debug=True)
