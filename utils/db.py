from flask_mysqldb import MySQL
mysql = MySQL()
def get_cursor():
    return mysql.connection.cursor(MySQLdb.cursors.DictCursor)
def set_mysql_timezone():
    cur = mysql.connection.cursor()
    cur.execute("SET time_zone = '+05:30'")
    cur.close()


