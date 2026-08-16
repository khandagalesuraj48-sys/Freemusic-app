from flask import Flask, jsonify, request
from flask_cors import CORS
from search_engine import search

app = Flask(__name__)
CORS(app)

@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "service": "JioSaavn API",
        "search": "/api/search?q=<query>"
    })

@app.get("/api/search")
def api_search():
    query = request.args.get("q") or request.args.get("query") or ""
    query = query.strip()

    if not query:
        return jsonify([])

    try:
        return jsonify(search(query))
    except Exception as exc:
        app.logger.exception("Search failed")
        return jsonify({
            "error": "JioSaavn search failed",
            "message": str(exc)
        }), 502

@app.get("/search")
def legacy_search():
    return api_search()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100)
