from flask import Flask, render_template
from utils.db import mysql

app = Flask(__name__)
app.config.from_pyfile("config.py")

mysql.init_app(app)
app.secret_key = app.config["SECRET_KEY"]

# 🔥 FORCE MYSQL TIMEZONE TO IST
with app.app_context():
    from utils.db import set_mysql_timezone
    set_mysql_timezone()

from routes.auth import auth_bp
app.register_blueprint(auth_bp)

from routes.restaurant import restaurant_bp
app.register_blueprint(restaurant_bp)

from routes.browse import browse_bp
app.register_blueprint(browse_bp)

from routes.order import order_bp
app.register_blueprint(order_bp)

from routes.savings import savings_bp
app.register_blueprint(savings_bp)

from routes.secret import secret_bp
app.register_blueprint(secret_bp)

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run()
