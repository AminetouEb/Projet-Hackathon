from flask import Flask, jsonify
import psycopg2
import os

app = Flask(__name__)

def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

@app.route("/test")
def test():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM environmental_footprint;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    return jsonify({"rows": count})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)