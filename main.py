from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import requests

from pdf_report import generate_pdf_report

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

VALUATION_API_URL = os.getenv("VALUATION_API_URL", "")
VALUATION_API_KEY = os.getenv("VALUATION_API_KEY", "")

DEFAULT_AGENT_FEE_PERCENT = 0.012
DEFAULT_CONVEYANCING = 1500
DEFAULT_REMOVALS = 800
DEFAULT_MISC = 500
DEFAULT_AFFORDABILITY_MULTIPLE = 4.5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
REPORTS_DIR = os.path.join(BASE_DIR, "Generated_reports")

os.makedirs(REPORTS_DIR, exist_ok=True)


def to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def estimate_moving_costs(estimated_value: float, extra_override: float = 0) -> dict:
    agent_fee = estimated_value * DEFAULT_AGENT_FEE_PERCENT
    conveyancing = DEFAULT_CONVEYANCING
    removals = DEFAULT_REMOVALS
    misc = DEFAULT_MISC
    base_total = agent_fee + conveyancing + removals + misc
    total = base_total + max(extra_override, 0)

    return {
        "agent_fee": round(agent_fee),
        "conveyancing": round(conveyancing),
        "removals": round(removals),
        "misc": round(misc),
        "extra_override": round(max(extra_override, 0)),
        "total": round(total),
    }


def get_result_type(plan: str, net_proceeds: float, max_budget: float, target_price: float = 0) -> str:
    if net_proceeds <= 0:
        return "negative_equity_risk"

    if plan == "rent":
        return "renting_next"

    if target_price > 0:
        if max_budget >= target_price:
            return "can_afford_target"
        if max_budget >= target_price * 0.9:
            return "close_but_tight"
        return "budget_gap"

    if max_budget >= 0:
        return "general_affordable"

    return "needs_review"


def recommendation_text(result_type: str) -> str:
    mapping = {
        "negative_equity_risk": "Selling may be difficult unless your mortgage balance or costs are lower than estimated.",
        "renting_next": "You may be able to release funds from your sale, but your next-step affordability depends on your expected rent and timing.",
        "can_afford_target": "You appear to be in a position to afford your target price, subject to lender criteria and final selling costs.",
        "close_but_tight": "You may be close to affording your target, but the numbers look tight at current assumptions.",
        "budget_gap": "There appears to be a gap between your likely budget and your target price.",
        "general_affordable": "You may be in a position to move, depending on the property you choose and your mortgage terms.",
        "needs_review": "You may need to review your assumptions before deciding.",
    }
    return mapping.get(result_type, "You may need to review your assumptions before deciding.")


def get_mock_valuation(address: str, property_type=None) -> dict:
    base_values = {
        "flat": 220000,
        "terraced": 275000,
        "semi-detached": 325000,
        "detached": 450000,
    }

    estimated = base_values.get((property_type or "").lower(), 300000)

    return {
        "estimated_value": round(estimated),
        "low": round(estimated * 0.95),
        "high": round(estimated * 1.05),
        "confidence": "Medium",
        "address": address,
        "property_type": property_type or ""
    }


def get_real_valuation(address: str, property_type=None) -> dict:
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


@app.get("/")
def health():
    return jsonify({"status": "ok"})


@app.route("/reports/<path:filename>")
def get_report(filename):
    return send_from_directory(REPORTS_DIR, filename)


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
    mortgage = to_float(data.get("mortgage", 0))
    early_repayment_charge = to_float(data.get("early_repayment_charge", 0))
    extra_costs_override = to_float(data.get("extra_costs_override", 0))
    plan = (data.get("plan") or "").strip().lower()
    target_price = to_float(data.get("target_price", 0))
    income = to_float(data.get("income", 0))
    partner_income = to_float(data.get("partner_income", 0))
    current_monthly_payment = to_float(data.get("current_monthly_payment", 0))

    estimated_value = to_float(valuation.get("estimated_value", 0))
    low = to_float(valuation.get("low", 0))
    high = to_float(valuation.get("high", 0))
    confidence = valuation.get("confidence", "Medium")

    if estimated_value <= 0:
        return jsonify({"error": "Valid valuation data is required."}), 400

    moving_costs = estimate_moving_costs(estimated_value, extra_costs_override)
    total_costs = moving_costs["total"] + early_repayment_charge
    net_proceeds = estimated_value - mortgage - total_costs

    total_income = income + partner_income
    borrowing_power = 0 if plan == "rent" else total_income * DEFAULT_AFFORDABILITY_MULTIPLE
    max_budget = max(net_proceeds, 0) + borrowing_power

    monthly_payment_estimate = None
    if plan != "rent" and borrowing_power > 0:
        loan_needed = max(max_budget - max(net_proceeds, 0), 0)
        monthly_payment_estimate = round(loan_needed * 0.006)

    monthly_payment_change = None
    if monthly_payment_estimate is not None and current_monthly_payment > 0:
        monthly_payment_change = round(monthly_payment_estimate - current_monthly_payment)

    result_type = get_result_type(
        plan=plan,
        net_proceeds=net_proceeds,
        max_budget=max_budget,
        target_price=target_price
    )

    recommendation = recommendation_text(result_type)

    return jsonify({
        "valuation": {
            "estimated_value": round(estimated_value),
            "low": round(low),
            "high": round(high),
            "confidence": confidence
        },
        "plan": plan,
        "moving_costs": moving_costs,
        "early_repayment_charge": round(early_repayment_charge),
        "net_proceeds": round(net_proceeds),
        "income": round(income),
        "partner_income": round(partner_income),
        "total_income": round(total_income),
        "borrowing_power": round(borrowing_power),
        "target_price": round(target_price),
        "max_budget": round(max_budget),
        "monthly_payment_estimate": monthly_payment_estimate,
        "monthly_payment_change": monthly_payment_change,
        "result_type": result_type,
        "recommendation": recommendation
    })


@app.post("/lead")
def lead():
    data = request.get_json(force=True)

    print("PROJECT 4 INCOMING DATA:", data)
    print("PROJECT 4 ADDRESS VALUE:", repr(data.get("address")))

    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    help_requested = data.get("help_requested") or []

    if not full_name or not email:
        return jsonify({"error": "Full name and email are required."}), 400
    if not address:
        return jsonify({"error": "Address is required."}), 400

    try:
        lead_id = int(datetime.now().timestamp())
        filename = f"report_{lead_id}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        selected_services = []
        if isinstance(help_requested, list):
            selected_services = help_requested
        elif isinstance(help_requested, str) and help_requested.strip():
            selected_services = [help_requested.strip()]

        pdf_data = {
            "name": full_name,
            "email": email,
            "address": address,
            "valuation_low": to_float(data.get("valuation_low", 0)),
            "valuation_high": to_float(data.get("valuation_high", 0)),
            "moving_costs": to_float(data.get("moving_costs", 0)),
            "net_proceeds": to_float(data.get("net_proceeds", 0)),
            "borrowing_power": to_float(data.get("borrowing_power", 0)),
            "max_budget": to_float(data.get("max_budget", 0)),
            "recommendation": data.get("recommendation") or "No recommendation available.",
            "selected_services": selected_services,
        }

        logo_path = os.path.join(STATIC_DIR, "logo.png")
        if not os.path.exists(logo_path):
            logo_path = None

        print("BASE_DIR:", BASE_DIR)
        print("STATIC_DIR:", STATIC_DIR)
        print("LOGO PATH:", logo_path)
        print("LOGO EXISTS:", os.path.exists(logo_path) if logo_path else False)

        generate_pdf_report(
            report_data=pdf_data,
            filepath=filepath,
            logo_path=logo_path
        )

        pdf_url = f"/reports/{filename}"

        try:
            booking_payload = {
                "name": full_name,
                "email": email,
                "phone": phone,
                "address": address,
                "valuation": int(to_float(data.get("valuation_high", 0))),
                "source": "property_tool",
                "created_at": datetime.now().isoformat(),
                "notes": f"PDF report: {pdf_url}"
            }
            print("BOOKING PAYLOAD:", booking_payload)

            requests.post(
                "https://booking-system-b13f.onrender.com/save-lead",
                json=booking_payload,
                timeout=10
            )
        except Exception as e:
            print("Booking save failed:", e)

        return jsonify({
            "success": True,
            "message": "Lead received and PDF generated.",
            "lead": {
                "lead_id": lead_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "help_requested": help_requested,
                "pdf_path": filepath,
                "pdf_url": pdf_url
            }
        })

    except Exception as e:
        return jsonify({"error": f"Failed to create lead report: {str(e)}"}), 500


@app.post("/lead-action")
def lead_action():
    data = request.get_json(force=True)

    email = (data.get("email") or "").strip().lower()
    action = (data.get("action") or "").strip()

    if not email:
        return jsonify({"error": "Email required"}), 400

    if action not in ["valuation_requested", "contact_requested"]:
        return jsonify({"error": "Invalid action"}), 400

    try:
        payload = {
            "email": email,
            "lead_stage": action,
            "is_hot_lead": True,
            "actioned_at": datetime.now().isoformat()
        }

        print("LEAD ACTION:", payload)

        with open("lead_actions_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{payload}\n")

        return jsonify({
            "success": True,
            "message": "Lead action recorded",
            "lead": payload
        })

    except Exception as e:
        print("Lead action failed:", e)
        return jsonify({"error": "Failed to log action"}), 500

if __name__ == "__main__":
    app.run(debug=True)