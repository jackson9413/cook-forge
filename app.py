#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cook-forge - local-first recipe technique and timing analyser.

Flask API + static UI. No API keys, no network calls, no LLM.
"""

import os
import json
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory, Response

import engine
import db
import samples

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), static_url_path="/static")

db.init_db()


@app.after_request
def add_headers(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "cook-forge", "time": datetime.now().isoformat(timespec="seconds")})


@app.route("/api/samples")
def list_samples():
    return jsonify([
        {"id": s["id"], "name": s["name"], "note": s["note"]} for s in samples.SAMPLES
    ])


@app.route("/api/sample")
def get_sample():
    sid = request.args.get("id", "")
    sample = samples.get_sample(sid)
    if not sample:
        return jsonify({"error": "sample not found"}), 404
    return jsonify(sample)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    payload = request.get_json(silent=True) or {}
    recipe_text = (payload.get("recipe") or "").strip()
    if not recipe_text:
        return jsonify({"error": "Paste a recipe first."}), 400
    context = {
        "gear": payload.get("gear") or "",
        "target_servings": payload.get("target_servings"),
        "intent": payload.get("intent") or "balanced",
        "time_available": payload.get("time_available"),
    }
    result = engine.analyze(recipe_text, context)
    session_id = None
    if payload.get("save", True):
        try:
            session_id = db.save_session(result, recipe_text)
        except Exception as exc:  # storage must never break an analysis
            app.logger.warning("could not save session: %s", exc)
    result["session_id"] = session_id
    return jsonify(result)


@app.route("/api/sessions")
def sessions_list():
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    return jsonify(db.list_sessions(limit))


@app.route("/api/sessions/<int:session_id>")
def session_get(session_id):
    row = db.get_session(session_id)
    if not row:
        return jsonify({"error": "session not found"}), 404
    return jsonify(row)


@app.route("/api/sessions/<int:session_id>", methods=["PATCH"])
def session_patch(session_id):
    payload = request.get_json(silent=True) or {}
    ok = db.update_session(session_id, rating=payload.get("rating"), notes=payload.get("notes"))
    if not ok:
        return jsonify({"error": "session not found"}), 404
    return jsonify(db.get_session(session_id))


@app.route("/api/export/<int:session_id>")
def export(session_id):
    row = db.get_session(session_id)
    if not row:
        return jsonify({"error": "session not found"}), 404
    fmt = (request.args.get("fmt") or "md").lower()
    result = row.get("result") or {}
    if fmt == "json":
        body = engine.to_json(result)
        mime = "application/json"
        ext = "json"
    else:
        body = engine.export_markdown(result)
        mime = "text/markdown"
        ext = "md"
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "" for ch in (result.get("title") or "recipe"))
    filename = ("cook-forge-%s.%s" % (safe.strip().replace(" ", "-") or "recipe", ext))
    return Response(body, mimetype=mime, headers={
        "Content-Disposition": 'attachment; filename="%s"' % filename
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5057))
    print("cook-forge running on http://127.0.0.1:%d" % port)
    app.run(host="127.0.0.1", port=port, debug=False)
