# -*- coding: utf-8 -*-
"""PayPal sandbox: OAuth token + JPY order creation (intent=CAPTURE).

⚠️ Only creates the order and returns the approve link; NEVER auto-approves /
auto-captures (payment requires explicit user confirmation).

Usage:
  PAYPAL_CLIENT_ID=.. PAYPAL_CLIENT_SECRET=.. python3 paypal_billing.py get-token
  PAYPAL_CLIENT_ID=.. PAYPAL_CLIENT_SECRET=.. python3 paypal_billing.py create-order --amount-jpy 16500 --item-name "LYCEE POD020-LYB"
"""
import argparse
import json

from _common import load_secrets, http_request, basic_auth, JsbError

TOKEN_URL = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
ORDERS_URL = "https://api-m.sandbox.paypal.com/v2/checkout/orders"


def get_token(secrets=None):
    secrets = secrets or load_secrets()
    cid = secrets.get("PAYPAL_CLIENT_ID")
    sec = secrets.get("PAYPAL_CLIENT_SECRET")
    if not cid or not sec:
        raise JsbError("Missing PayPal credentials: set PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET")

    status, text = http_request(
        "POST", TOKEN_URL,
        headers={"Authorization": basic_auth(cid, sec),
                 "Content-Type": "application/x-www-form-urlencoded"},
        body="grant_type=client_credentials",
        use_proxy=False, timeout=25,
    )
    if status != 200:
        raise JsbError(f"PayPal OAuth failed HTTP {status}: {text[:200]}")
    data = json.loads(text)
    return {
        "access_token": data.get("access_token"),
        "token_type": data.get("token_type"),
        "expires_in": data.get("expires_in"),
        "scope": data.get("scope"),
    }


def create_order(amount_jpy, item_name, secrets=None):
    token = get_token(secrets)["access_token"]
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": "japan-shopping-buddy",
            "description": item_name,
            "amount": {"currency_code": "JPY", "value": f"{float(amount_jpy):.2f}"},
        }],
    }
    status, text = http_request(
        "POST", ORDERS_URL,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "Prefer": "return=representation"},
        body=json.dumps(body),
        use_proxy=False, timeout=25,
    )
    if status not in (200, 201):
        raise JsbError(f"PayPal Orders failed HTTP {status}: {text[:200]}")
    data = json.loads(text)
    approve = next((l["href"] for l in data.get("links", []) if l.get("rel") == "approve"), None)
    return {
        "order_id": data.get("id"),
        "status": data.get("status"),
        "amount": {"currency_code": "JPY", "value": f"{float(amount_jpy):.2f}"},
        "item_name": item_name,
        "approve_link": approve,
        "note": "Order created (NOT charged). The user must open approve_link to authorize the payment; never auto-approve/capture.",
    }


def get_order(order_id, secrets=None):
    """Query order status (read-only, no charge). Must be checked before capture to avoid double charging."""
    token = get_token(secrets)["access_token"]
    status, text = http_request(
        "GET", f"{ORDERS_URL}/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
        use_proxy=False, timeout=25,
    )
    if status != 200:
        raise JsbError(f"PayPal order query failed HTTP {status}: {text[:200]}")
    data = json.loads(text)
    return {
        "order_id": data.get("id"),
        "status": data.get("status"),
        "intent": data.get("intent"),
        "note": "Read-only query: does not change the order status and does not charge.",
    }


def capture_order(order_id, secrets=None):
    """Capture an approved order (the real charge). Idempotent: a COMPLETED order is never retried."""
    before = get_order(order_id, secrets)
    if before["status"] == "COMPLETED":
        return {"order_id": order_id, "status": "COMPLETED", "already_captured": True,
                "note": "Order already captured; no duplicate charge (idempotent)."}
    if before["status"] != "APPROVED":
        raise JsbError(f"Order status {before['status']} cannot be captured: the user must approve in the sandbox first (not approved yet)")

    token = get_token(secrets)["access_token"]
    status, text = http_request(
        "POST", f"{ORDERS_URL}/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "Prefer": "return=representation"},
        body="{}",
        use_proxy=False, timeout=25,
    )
    if status not in (200, 201):
        raise JsbError(f"PayPal capture failed HTTP {status}: {text[:200]}")
    data = json.loads(text)
    capture = (data.get("purchase_units") or [{}])[0].get("payments", {}).get("captures", [{}])
    capture_id = capture[0].get("id") if capture else None
    amount = capture[0].get("amount", {}) if capture else {}
    return {
        "order_id": data.get("id"),
        "status": data.get("status"),
        "capture_id": capture_id,
        "amount": amount,
        "already_captured": False,
        "note": "Captured after explicit user approval (real charge). Record capture_id in the confirmation sheet as proof.",
    }


def main():
    ap = argparse.ArgumentParser(description="PayPal sandbox orders")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("get-token")
    co = sub.add_parser("create-order")
    co.add_argument("--amount-jpy", type=float, required=True)
    co.add_argument("--item-name", default="Japanese product")
    go = sub.add_parser("get-order")
    go.add_argument("--order-id", required=True)
    cp = sub.add_parser("capture-order")
    cp.add_argument("--order-id", required=True)
    args = ap.parse_args()

    try:
        if args.cmd == "get-token":
            result = get_token()
        elif args.cmd == "create-order":
            result = create_order(args.amount_jpy, args.item_name)
        elif args.cmd == "get-order":
            result = get_order(args.order_id)
        else:
            result = capture_order(args.order_id)
    except JsbError as e:
        msg = str(e)
        if "credential" in msg.lower():
            code = "AUTH_MISSING"
        elif "HTTP" in msg:
            code = "HTTP_ERROR"
        else:
            code = "RESULT_UNKNOWN"
        print(json.dumps({"status": "error", "code": code, "error": msg},
                         ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
