import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

MYSQL_HOST = os.getenv("MYSQLHOST")
MYSQL_USER = os.getenv("MYSQLUSER")
MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD")
MYSQL_DB = os.getenv("MYSQLDATABASE")
MYSQL_PORT = int(os.getenv("MYSQLPORT", 3306))

MYSQL_CURSORCLASS = "DictCursor"

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "terminalplate@gmail.com")
