from datetime import date, datetime
from decimal import Decimal
from flask import Flask, request, jsonify
from flask_cors import CORS
import atexit
import os

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

_connection_pool: pool.ThreadedConnectionPool | None = None


def _db_params():
    """Construit la configuration DB depuis les variables d'environnement."""
    return {
        "host": os.getenv("DB_HOST", "db"),
        "database": os.getenv("DB_NAME", "environmental_db"),
        "user": os.getenv("DB_USER", "app_readonly"),
        "password": os.getenv("DB_PASSWORD", "1234"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "connect_timeout": 5,
    }


def get_pool() -> pool.ThreadedConnectionPool:
    """Initialise paresseusement un pool partage pour l'API Flask."""
    global _connection_pool
    if _connection_pool is None:
        params = _db_params()
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=12,
            **params,
        )
    return _connection_pool


@atexit.register
def _close_pool():
    """Ferme proprement le pool a l'arret du processus."""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None


def _json_val(v):
    """Convertit les types SQL non JSON-serialisables vers des types standards."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _row_to_hit(row: dict) -> dict:
    """
    Adapte une ligne SQL en contrat JSON stable pour le frontend.

    - Le champ interne `id` n'est pas expose.
    - `gwp_total` est renomme en `co2_kg` pour clarifier l'unite retournee.
    """
    out: dict = {}
    for k, v in row.items():
        if k == "id":
            continue
        if k == "gwp_total":
            out["co2_kg"] = float(v) if v is not None else None
            continue
        out[k] = _json_val(v)
    return out


@app.route("/calculate", methods=["POST"])
def calculate():
    """
    Recherche la meilleure correspondance machine et renvoie sa fiche JSON.

    Strategie:
    - recherche `ILIKE %machine%` pour accepter les saisies partielles,
    - tri par nom le plus court puis ordre alphabetique pour obtenir un resultat
      deterministe quand plusieurs lignes correspondent.
    """
    data = request.json or {}
    user_input = (data.get("machine") or "").strip()
    if not user_input:
        return jsonify({"error": "machine not found"}), 404

    p = get_pool()
    conn = p.getconn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT *
            FROM environmental_footprint
            WHERE name ILIKE %s
            ORDER BY char_length(name) ASC, name ASC
            LIMIT 1
            """,
            ("%" + user_input + "%",),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        p.putconn(conn)

    if not row:
        return jsonify({"error": "machine not found"}), 404

    return jsonify({"item": _row_to_hit(dict(row))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
