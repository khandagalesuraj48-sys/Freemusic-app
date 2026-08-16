
from flask import Flask, request, jsonify

from flask_cors import CORS

import jiosaavn



app = Flask(__name__)

CORS(app)



def search():

    query = request.args.get("query", "").strip()

    lyrics = request.args.get("lyrics", "false").lower() == "true"



    if not query:

        return jsonify({"value": [], "Count": 0})



    try:

        result = jiosaavn.search_for_song(query, lyrics, True)

        return jsonify(result)

    except Exception as e:

        return jsonify({

            "error": str(e),

            "value": [],

            "Count": 0

        }), 500



@app.route("/", methods=["GET"])

@app.route("/api", methods=["GET"])

@app.route("/api/index", methods=["GET"])

@app.route("/api/index/", methods=["GET"])

@app.route("/result/", methods=["GET"])

@app.route("/api/result/", methods=["GET"])

def api_search():

    return search()

