# -*- coding: utf-8 -*-
"""Smoke regression: Japan Shopping Buddy · PayPal edition (intl destinations + payment-safety contract).

Usage:
  python3 smoke_test.py            # full offline suite (no network, no PayPal credentials needed)
  python3 smoke_test.py --online   # add online cases (live FX / multi-currency conversion)

All assertions are based on the scripts' output contract: reviewers/judges can re-run this
directly as reproducible evidence.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
BASE_RATE = 0.04224

PASS, FAIL = [], []


def run(script, *args):
    p = subprocess.run([PY, os.path.join(HERE, script), *args],
                       capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout, p.stderr


def est(*args):
    code, out, err = run("arrival_price.py", *args)
    try:
        return code, json.loads(out)
    except json.JSONDecodeError:
        return code, {"_raw": out, "_err": err}


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  FAIL") + f"  {name}" + (f"  [{detail}]" if detail and not cond else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true", help="add online cases")
    online = ap.parse_args().online

    print("[1] FX (offline baseline)")
    code, out, _ = run("exchange_rate.py", "--baseline")
    d = json.loads(out) if code == 0 and out.strip() else {}
    check("FX CLI produces output", bool(d))
    check("baseline rate 0.04224", d.get("rate") == BASE_RATE)
    code, out, _ = run("exchange_rate.py", "--to", "USD", "--baseline")
    check("errors when non-CNY has no baseline (never guesses FX)", code != 0, out.strip()[:40])

    print("[2] Mainland China full postal-tax model")
    _, x = est("--price-jpy", "16500", "--destination", "cn", "--tariff-category", "textile", "--baseline")
    item = round(16500 * BASE_RATE, 2)
    check("textile 20% duty = goods x 20%", x["tariff"]["charged_cny"] == round(item * 0.2, 2), str(x["tariff"]["charged_cny"]))
    _, x = est("--price-jpy", "3520", "--destination", "cn", "--tariff-category", "it", "--baseline")
    check("due <= 50 CNY is exempt", x["tariff"]["exempt"] is True and x["tariff"]["charged_cny"] == 0)
    _, x = est("--price-jpy", "980000", "--destination", "cn", "--tariff-category", "it", "--baseline")
    check("over 1000 CNY limit warns", x.get("postal_limit", {}).get("exceeded") is True)

    print("[3] Hong Kong / Singapore")
    _, x = est("--price-jpy", "16500", "--destination", "hk", "--baseline")
    check("HK free port 0 tax", x["tariff"]["charged_cny"] == 0.0 and x["tariff"]["modeled"] is True)
    _, x = est("--price-jpy", "16500", "--destination", "sg", "--baseline")
    cif = x["breakdown_cny"]["item"] + x["breakdown_cny"]["domestic"] + x["breakdown_cny"]["forwarding"][0]
    check("SG GST 9% on CIF", x["tariff"]["charged_cny"] == round(cif * 0.09, 2),
          f"{x['tariff']['charged_cny']} vs {round(cif * 0.09, 2)}")
    check("SG modeled", x["tariff"]["modeled"] is True)

    print("[4] US / EU (offline: must declare no conversion when FX missing)")
    _, x = est("--price-jpy", "16500", "--destination", "us", "--baseline")
    check("US does not guess threshold without USD FX", x["tariff"]["modeled"] is False and "conversion" in x["tariff"]["category"],
          x["tariff"]["category"])
    _, x = est("--price-jpy", "16500", "--destination", "eu", "--vat-rate", "0.19", "--baseline")
    check("EU does not guess threshold without EUR FX", x["tariff"]["modeled"] is False, x["tariff"]["category"])
    _, x = est("--price-jpy", "16500", "--destination", "eu", "--baseline")
    check("EU prompts when --vat-rate missing", "vat-rate" in x["tariff"]["category"], x["tariff"]["category"])

    print("[5] other: not modeled")
    _, x = est("--price-jpy", "16500", "--destination", "other", "--baseline")
    check("other never invents tax", x["tariff"]["modeled"] is False and x["tariff"]["charged_cny"] == 0.0)

    print("[6] Payment-safety contract (no credentials)")
    code, out, _ = run("paypal_billing.py", "get-token")
    d = json.loads(out) if out.strip() else {}
    check("no credentials -> AUTH_MISSING", code != 0 and d.get("code") == "AUTH_MISSING", str(d.get("code")))
    code, out, _ = run("paypal_billing.py", "create-order", "--amount-jpy", "16500", "--item-name", "TEST")
    d = json.loads(out) if out.strip() else {}
    check("create-order refused without credentials, no order made", code != 0 and d.get("code") == "AUTH_MISSING")
    code, out, _ = run("paypal_billing.py", "--help")
    check("no approve subcommand (approve only via the sandbox link clicked by the user)", "approve" not in out.lower())
    check("capture requires explicit --order-id (never auto-charges)",
          "capture-order" in out and "--order-id" in run("paypal_billing.py", "capture-order", "--help")[1])
    check("all four subcommands present", all(k in out for k in ("get-token", "create-order", "get-order", "capture-order")))
    code, out, _ = run("paypal_billing.py", "capture-order", "--order-id", "TEST-ORDER")
    d = json.loads(out) if out.strip() else {}
    check("capture without credentials never charges (AUTH_MISSING)", code != 0 and d.get("code") == "AUTH_MISSING",
          str(d.get("code")))

    print("[7] Confirmation sheet (payment sheet + source table)")
    qf = "/tmp/_smoke_paypal_quote.md"
    _, x = est("--price-jpy", "16500", "--destination", "hk", "--quote", "--quote-type", "payment",
               "--quote-file", qf, "--item-name", "LYCEE YUKATA", "--baseline")
    md = open(qf, encoding="utf-8").read() if os.path.exists(qf) else ""
    check("title is the payment confirmation sheet", md.startswith("# Payment Confirmation Sheet"))
    for kw in ("Ship-to", "Calculation basis & data sources", "Estimate disclaimer", "User confirms item & amounts"):
        check(f"sheet contains \"{kw}\"", kw in md)
    check("JSON contract fields present", all(k in x for k in (
        "breakdown_cny", "channel", "data_sources", "destination", "estimate_note",
        "item", "provenance", "rate", "status", "tariff", "total_cny")))

    print("[8] Input validation")
    for args, name, want in (
        (["--price-jpy", "0", "--baseline"], "rejects price 0", "json"),
        (["--price-jpy", "16500", "--destination", "uk"], "rejects bad destination", "cli"),
        (["--price-jpy", "16500", "--tariff-category", "xxx"], "rejects unknown category", "cli"),
    ):
        code, x = est(*args)
        if want == "json":
            check(name, code != 0 and x.get("code") == "BAD_INPUT", f"exit={code}")
        else:
            check(name, code == 2, f"exit={code}")

    if online:
        print("[9] Online: intl thresholds & multi-currency")
        _, x = est("--price-jpy", "126000", "--destination", "us")
        check("JPY 126,000 ~= $796 within USD 800 de minimis", x["tariff"]["modeled"] is True and x["tariff"]["charged_cny"] == 0.0,
              x["tariff"]["category"])
        _, x = est("--price-jpy", "127000", "--destination", "us")
        check("JPY 127,000 ~= $802 above de minimis -> not modeled", x["tariff"]["modeled"] is False, x["tariff"]["category"])
        _, x = est("--price-jpy", "26000", "--destination", "eu", "--vat-rate", "0.19")
        check("JPY 26,000 ~= EUR 147 within IOSS threshold, VAT charged", x["tariff"]["modeled"] is True and x["tariff"]["charged_cny"] > 0,
              x["tariff"]["category"])
        _, x = est("--price-jpy", "27000", "--destination", "eu", "--vat-rate", "0.19")
        check("JPY 27,000 ~= EUR 153 above threshold -> not modeled", x["tariff"]["modeled"] is False, x["tariff"]["category"])

    print()
    print(f"result: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("failed: " + "; ".join(FAIL))
        sys.exit(1)


if __name__ == "__main__":
    main()
