
import sys

from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from flask import Flask, request, jsonify

from flask_cors import CORS

import jiosaavn



app = Flask(__name__)

CORS(app)



@app.route("/api/index", methods=["GET"])

@app.route("/api/index/", methods=["GET"])

@app.route("/api/result", methods=["GET"])

@app.route("/api/result/", methods=["GET"])

def search_api():

    query = request.args.get("query", "").strip()

    lyrics = request.args.get("lyrics", "false").lower() == "true"



    if not query:

        return jsonify({"value": [], "Count": 0})



    try:

        result = jiosaavn.search_for_song(query, lyrics, True)

        return jsonify(result)

    except Exception as e:

        return jsonify({

            "value": [],

            "Count": 0,

            "error": str(e)

        }), 500



@app.route("/", methods=["GET"])

def health():

    return jsonify({

        "status": "ok",

        "service": "JioSaavnAPI"

    })

