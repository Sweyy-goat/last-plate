from flask_mysqldb import MySQL
mysql = MySQL()
def set_mysql_timezone():
    cur = mysql.connection.cursor()
    cur.execute("SET time_zone = '+06:30'")
    cur.close()


