"""
Flask app: HTTP routes only. All database and business logic live in backend.py.
Serves login.html and discontinuation.html so frontend and API share the same origin.
"""

import os
from flask import Flask, request, jsonify, send_from_directory, redirect

import backend

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# POST /login — mobile must be in DB; OTP simulated. Body: { mobile } or { mobile, otp }
# ---------------------------------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    mobile = data.get("mobile")
    otp = data.get("otp")  # None for "send OTP" step
    result = backend.do_login(mobile, otp)
    if result.get("registered") is False and "message" in result:
        return jsonify(result), 404
    return jsonify(result)


# ---------------------------------------------------------------------------
# POST /topup — activate/renew pass; optional activationCode
# ---------------------------------------------------------------------------
@app.route("/topup", methods=["POST"])
def topup():
    data = request.get_json(silent=True) or {}
    result = backend.do_topup(
        card_number=data.get("cardNumber"),
        holder_name=data.get("holderName"),
        mobile_number=data.get("mobileNumber"),
        plan_type=(data.get("planType") or "").upper(),
        activation_code=data.get("activationCode"),
    )
    if result.get("status") == "error" and "cardNumber and planType" in result.get("message", ""):
        return jsonify(result), 400
    if result.get("status") == "error" and "Invalid planType" in result.get("message", ""):
        return jsonify(result), 400
    if result.get("status") == "error" and "discontinued" in result.get("message", "").lower():
        return jsonify(result), 400
    if result.get("status") == "error":
        return jsonify(result), 500
    return jsonify(result)


# ---------------------------------------------------------------------------
# GET /status/<cardNumber> — return pass status (includes activationCode)
# ---------------------------------------------------------------------------
@app.route("/status/<card_number>", methods=["GET"])
def status(card_number):
    result = backend.get_status(card_number)
    if result.get("status") == "error":
        return jsonify(result), 500
    return jsonify(result)


# ---------------------------------------------------------------------------
# POST /validate — check if card is valid (no trip deduction)
# ---------------------------------------------------------------------------
@app.route("/validate", methods=["POST"])
def validate_pass():
    data = request.get_json(silent=True) or {}
    result = backend.validate_card(data.get("cardNumber"))
    if result.get("status") == "error":
        return jsonify(result), 400
    return jsonify(result)


# ---------------------------------------------------------------------------
# POST /use-trip — deduct one trip
# ---------------------------------------------------------------------------
@app.route("/use-trip", methods=["POST"])
def use_trip():
    data = request.get_json(silent=True) or {}
    result = backend.use_trip(data.get("cardNumber"))
    if result.get("status") == "error":
        return jsonify(result), 400
    return jsonify(result)


# ---------------------------------------------------------------------------
# POST /discontinue — mark card DISCONTINUED
# ---------------------------------------------------------------------------
@app.route("/discontinue", methods=["POST"])
def discontinue():
    data = request.get_json(silent=True) or {}
    result = backend.discontinue_card(data.get("cardNumber"))
    if result.get("status") == "error":
        return jsonify(result), 400
    return jsonify(result)


# ---------------------------------------------------------------------------
# Serve HTML pages (same origin as API)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect("/login.html")


@app.route("/login.html")
def serve_login():
    return send_from_directory(BASE_DIR, "login.html")


@app.route("/discontinuation.html")
def serve_discontinuation():
    return send_from_directory(BASE_DIR, "discontinuation.html")


if __name__ == "__main__":
    backend.init_db()
    app.run(debug=True)
