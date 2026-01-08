from flask import Flask
from utils.db import mysql

app = Flask(__name__)
app.config.from_pyfile("config.py")

mysql.init_app(app)
app.secret_key = app.config["SECRET_KEY"]

from routes.auth import auth_bp
app.register_blueprint(auth_bp)
from routes.restaurant import restaurant_bp
app.register_blueprint(restaurant_bp)

from routes.browse import browse_bp
app.register_blueprint(browse_bp)
from routes.order import order_bp
app.register_blueprint(order_bp)


from flask import render_template

@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run()

