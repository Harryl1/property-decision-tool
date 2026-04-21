from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import requests

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

VALUATION_API_URL = os.getenv("VALUATION_API_URL", "")
VALUATION_API_KEY = os.getenv("VALUATION_API_KEY", "")

DEFAULT_AGENT_FEE_PERCENT = 0.012
DEFAULT_CONVEYANCING = 1500
DEFAULT_REMOVALS = 800
DEFAULT_MISC = 500
DEFAULT_AFFORDABILITY_MULTIPLE = 4.5

REPORTS_DIR = "generated_reports"


def generate_pdf_report(data, lead_id):
    if os.path.exists(REPORTS_DIR) and not os.path.isdir(REPORTS_DIR):
        raise Exception(f"'{REPORTS_DIR}' exists but is not a folder.")

    os.makedirs(REPORTS_DIR, exist_ok=True)

    filename = f"report_{lead_id}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    y = height - 50

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "Your Property Report")

    y -= 40
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Generated: {datetime.now().strftime('%d/%m/%Y')}")

    y -= 30
    c.drawString(50, y, f"Name: {data.get('name', '')}")
    y -= 20
    c.drawString(50, y, f"Email: {data.get('email', '')}")
    y -= 20
    c.drawString(50, y, f"Address: {data.get('address', '')}")

    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Results Summary")

    y -= 30
    c.setFont("Helvetica", 12)
    c.drawString(
        50,
        y,
        f"Valuation Range: £{data.get('valuation_low', 0):,.0f} - £{data.get('valuation_high', 0):,.0f}"
    )
    y -= 20
    c.drawString(50, y, f"Moving Costs: £{data.get('moving_costs', 0):,.0f}")
    y -= 20
    c.drawString(50, y, f"Net Proceeds: £{data.get('net_proceeds', 0):,.0f}")
    y -= 20
    c.drawString(50, y, f"Borrowing Power: £{data.get('borrowing_power', 0):,.0f}")
    y -= 20
    c.drawString(50, y, f"Max Budget: £{data.get('max_budget', 0):,.0f}")

    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Recommendation")

    y -= 25
    c.setFont("Helvetica", 12)
    recommendation = data.get("recommendation", "No recommendation available.")
    c.drawString(50, y, recommendation[:100])

    c.save()

    return filepath


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


@app.route("/reports/<filename>")
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
    mortgage = float(data.get("mortgage", 0) or 0)
    early_repayment_charge = float(data.get("early_repayment_charge", 0) or 0)
    extra_costs_override = float(data.get("extra_costs_override", 0) or 0)
    plan = (data.get("plan") or "").strip().lower()
    target_price = float(data.get("target_price", 0) or 0)
    income = float(data.get("income", 0) or 0)
    partner_income = float(data.get("partner_income", 0) or 0)
    current_monthly_payment = float(data.get("current_monthly_payment", 0) or 0)

    estimated_value = float(valuation.get("estimated_value", 0) or 0)
    low = float(valuation.get("low", 0) or 0)
    high = float(valuation.get("high", 0) or 0)
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

        pdf_data = {
            "name": full_name,
            "email": email,
            "address": address,
            "valuation_low": float(data.get("valuation_low", 0) or 0),
            "valuation_high": float(data.get("valuation_high", 0) or 0),
            "moving_costs": float(data.get("moving_costs", 0) or 0),
            "net_proceeds": float(data.get("net_proceeds", 0) or 0),
            "borrowing_power": float(data.get("borrowing_power", 0) or 0),
            "max_budget": float(data.get("max_budget", 0) or 0),
            "recommendation": data.get("recommendation", "No recommendation available.")
        }

        pdf_path = generate_pdf_report(pdf_data, lead_id)
        filename = os.path.basename(pdf_path)
        pdf_url = f"/reports/{filename}"

        try:
            booking_payload = {
                "name": full_name,
                "email": email,
                "phone": phone,
                "address": (data.get("address") or "").strip(),
                "valuation": int(float(data.get("valuation_high", 0) or 0)),
                "source": "property_tool",
                "created_at": datetime.now().isoformat(),
                "notes": f"PDF report: {pdf_url}"
            }

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
                "pdf_path": pdf_path,
                "pdf_url": pdf_url
            }
        })

    except Exception as e:
        return jsonify({"error": f"Failed to create lead report: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)