from flask_mysqldb import MySQL
mysql = MySQL()
@app.before_request
def set_timezone():
    cur = mysql.connection.cursor()
    cur.execute("SET time_zone = '+05:30'")
    cur.close()
