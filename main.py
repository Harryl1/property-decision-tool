from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests

app = Flask(__name__)

# Allow requests from your Carrd site
CORS(app, resources={r"/*": {"origins": "*"}})

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

VALUATION_API_URL = os.getenv("VALUATION_API_URL", "")
VALUATION_API_KEY = os.getenv("VALUATION_API_KEY", "")

# Change this later if you want more realistic logic
DEFAULT_AGENT_FEE_PERCENT = 0.012   # 1.2%
DEFAULT_CONVEYANCING = 1500
DEFAULT_REMOVALS = 800
DEFAULT_MISC = 500
DEFAULT_AFFORDABILITY_MULTIPLE = 4.5


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

def estimate_moving_costs(estimated_value: float) -> dict:
    agent_fee = estimated_value * DEFAULT_AGENT_FEE_PERCENT
    conveyancing = DEFAULT_CONVEYANCING
    removals = DEFAULT_REMOVALS
    misc = DEFAULT_MISC
    total = agent_fee + conveyancing + removals + misc

    return {
        "agent_fee": round(agent_fee),
        "conveyancing": round(conveyancing),
        "removals": round(removals),
        "misc": round(misc),
        "total": round(total),
    }


def recommendation_text(max_budget: float, estimated_value: float, net_proceeds: float) -> str:
    if net_proceeds <= 0:
        return "Selling may be difficult unless your mortgage balance or costs are lower than estimated."
    if max_budget >= estimated_value * 1.15:
        return "You could be in a strong position to move and increase your budget."
    if max_budget >= estimated_value:
        return "You may be in a position to move, depending on your next property and mortgage terms."
    return "You may need to review your onward budget or wait before moving."


def get_mock_valuation(address: str, property_type: str | None = None) -> dict:
    # Temporary mock response for testing
    return {
        "estimated_value": 300000,
        "low": 285000,
        "high": 315000,
        "confidence": "Medium",
        "address": address,
        "property_type": property_type or ""
    }


def get_real_valuation(address: str, property_type: str | None = None) -> dict:
    """
    Replace this with your real valuation API request shape.
    """
    if not VALUATION_API_URL:
        return get_mock_valuation(address, property_type)

    headers = {
        "Authorization": f"Bearer {VALUATION_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "address": address,
        "property_type": property_type,
    }

    response = requests.post(VALUATION_API_URL, json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    raw = response.json()

    # Adjust mapping to your provider's actual response keys
    estimated = float(raw.get("estimated_value", 0))
    low = float(raw.get("low", estimated * 0.95))
    high = float(raw.get("high", estimated * 1.05))
    confidence = raw.get("confidence", "Medium")

    return {
        "estimated_value": round(estimated),
        "low": round(low),
        "high": round(high),
        "confidence": confidence,
        "address": address,
        "property_type": property_type or ""
    }


# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------

@app.route("/")
def home():
    return {"status": "ok"}

@app.get("/")
def health():
    return jsonify({"status": "ok"})


@app.post("/value")
def value():
    data = request.get_json(force=True)

    address = (data.get("address") or "").strip()
    property_type = (data.get("property_type") or "").strip()

    if not address:
        return jsonify({"error": "Address is required."}), 400

    try:
        valuation = get_real_valuation(address, property_type)
        return jsonify(valuation)
    except requests.RequestException as e:
        return jsonify({"error": f"Valuation API request failed: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.post("/calculate")
def calculate():
    data = request.get_json(force=True)

    valuation = data.get("valuation") or {}
    mortgage = float(data.get("mortgage", 0) or 0)
    income = float(data.get("income", 0) or 0)
    partner_income = float(data.get("partner_income", 0) or 0)

    estimated_value = float(valuation.get("estimated_value", 0) or 0)
    low = float(valuation.get("low", 0) or 0)
    high = float(valuation.get("high", 0) or 0)
    confidence = valuation.get("confidence", "Medium")

    if estimated_value <= 0:
        return jsonify({"error": "Valid valuation data is required."}), 400

    moving_costs = estimate_moving_costs(estimated_value)
    total_income = income + partner_income
    borrowing_power = total_income * DEFAULT_AFFORDABILITY_MULTIPLE
    net_proceeds = estimated_value - mortgage - moving_costs["total"]
    max_budget = max(net_proceeds, 0) + borrowing_power

    monthly_payment_estimate = None
    if max_budget > max(net_proceeds, 0):
        loan_needed = max(max_budget - max(net_proceeds, 0), 0)
        # Very rough estimate: not mortgage advice
        monthly_payment_estimate = round((loan_needed * 0.006))

    recommendation = recommendation_text(
        max_budget=max_budget,
        estimated_value=estimated_value,
        net_proceeds=net_proceeds
    )

    return jsonify({
        "valuation": {
            "estimated_value": round(estimated_value),
            "low": round(low),
            "high": round(high),
            "confidence": confidence
        },
        "moving_costs": moving_costs,
        "mortgage_remaining": round(mortgage),
        "income": round(income),
        "partner_income": round(partner_income),
        "total_income": round(total_income),
        "borrowing_power": round(borrowing_power),
        "net_proceeds": round(net_proceeds),
        "max_budget": round(max_budget),
        "monthly_payment_estimate": monthly_payment_estimate,
        "recommendation": recommendation
    })


if __name__ == "__main__":
    app.run(debug=True)