from flask import Flask, request, jsonify
import psycopg2

app = Flask(__name__)

def db():
    return psycopg2.connect(
        host="db",
        database="carbon",
        user="admin",
        password="admin"
    )

# 🔥 recherche machine + calcul CO2
@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json
    user_input = data["machine"]

    conn = db()
    cur = conn.cursor()

    # 🔎 recherche simple dans le nom
    cur.execute("""
        SELECT name, gwp_total
        FROM carbon_data
        WHERE name ILIKE %s
        LIMIT 1
    """, ('%' + user_input + '%',))

    result = cur.fetchone()

    cur.close()
    conn.close()

    if result:
        return jsonify({
            "machine": result[0],
            "co2_kg": result[1]
        })
    else:
        return jsonify({
            "error": "machine not found"
        })

app.run(host="0.0.0.0", port=5000)
