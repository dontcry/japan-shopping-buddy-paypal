# -*- coding: utf-8 -*-
"""Landed-cost estimate: item price + Japan domestic shipping + forwarding shipping + handling fee + import duty, all converted to CNY (estimate).

Formula: references/price_formula.md; forwarding rates: references/forwarding_rates.md.

Usage:
  python3 arrival_price.py --price-jpy 16500
  python3 arrival_price.py --price-jpy 16500 --channel echina --domestic-jpy 660
  python3 arrival_price.py --price-jpy 16500 --baseline   # built-in baseline FX, no network
  python3 arrival_price.py --price-jpy 33000 --quote \
      --item-name "ace GENE CB2 backpack 20025" --platform "Rakuten / Amazon Japan" \
      --condition "New" --confidence "High" --quote-file quote.md   # render full confirmation sheet
"""
import argparse
import datetime
import json

import exchange_rate
from _common import JsbError

# Forwarding rates (Tsusso Japan China lanes, JPY; anonymized from azone measurements, marked as estimates)
FORWARDING = {
    "echina": {"label": "eCHINA", "range": (1500, 2600), "days": "~1 week", "note": "cheapest"},
    "ems": {"label": "EMS", "range": (2200, 2800), "days": "3-7 days", "note": "most reliable, insured"},
    "sf": {"label": "SF CHINA", "range": (2950, 3600), "days": "-", "note": "expensive"},
    "ship": {"label": "Sea freight", "range": (1800, 2200), "days": "1-2 months", "note": "slow"},
}
HANDLING_FEE = (300, 550)      # forwarding handling fee JPY/parcel
DEFAULT_RATE = 0.04224

# Postal import tax per PRC "Duty Rate Table for Personal Inbound Articles" (bands 1/2/3 = 13%/20%/50%)
TARIFF_PRESETS = {
    # Band 1 - 13%
    "it": {"label": "Books/educational AV; IT products (PC/phone/camera)", "rate": 0.13},
    "food": {"label": "Food/beverages/medicine", "rate": 0.13},
    "precious_metal": {"label": "Gold/silver articles", "rate": 0.13},
    "furniture": {"label": "Furniture", "rate": 0.13},
    "toy": {"label": "Toys/games/festival or leisure items", "rate": 0.13},
    "sports": {"label": "Sports goods (excl. golf)/fishing gear", "rate": 0.13},
    # Band 2 - 20%
    "textile": {"label": "Textiles & made-ups (clothing/footwear/bags)", "rate": 0.20},
    "appliance": {"label": "Camcorders & other electrical appliances", "rate": 0.20},
    "bike": {"label": "Bicycles", "rate": 0.20},
    "other": {"label": "Other items not in bands 1/3 (cosmetics/toiletries etc.)", "rate": 0.20},
    # Band 3 - 50%
    "tobacco_alcohol": {"label": "Tobacco/alcohol", "rate": 0.50},
    "jewelry": {"label": "Precious jewelry & gemstones", "rate": 0.50},
    "golf": {"label": "Golf balls & equipment", "rate": 0.50},
    "luxury": {"label": "Luxury watches/high-end cosmetics", "rate": 0.50},
}
DEFAULT_TARIFF_RATE = 0.20     # fallback: band 2 "other items"
TARIFF_EXEMPT_THRESHOLD = 50.0  # duty <= 50 CNY is exempt (personal postal articles)
POSTAL_LIMIT_CNY = 1000.0      # per-parcel limit 1000 CNY (800 for HK/MO/TW)

# Destination rules: CN fully modeled; HK/others get a framework only, explicitly marked not-modeled, never invented numbers
DESTINATIONS = {
    "cn": {
        "label": "Mainland China", "tax_model": "personal_postal", "limit_cny": POSTAL_LIMIT_CNY,
        "basis": "Postal import tax per PRC GACC duty table bands 1/2/3 (13%/20%/50%, since 2019-04-09); "
                 "duty <= 50 CNY exempt and per-parcel limit 1000 CNY (800 for HK/MO/TW) per GACC Announcement 2010 No. 43",
    },
    "hk": {
        "label": "Hong Kong, China", "tax_model": "free_port", "limit_cny": None,
        "basis": "HK is a free port: no import duty or VAT on general goods (tobacco, alcohol, fuel etc. dutiable excepted)",
    },
    "us": {
        "label": "United States", "tax_model": "de_minimis", "currency": "USD", "threshold_local": 800.0,
        "basis": "US USD 800 de minimis (19 U.S.C. 1321): duty-free within threshold; above it duty per HTS "
                 "classification; state/local sales tax not modeled by this script",
    },
    "eu": {
        "label": "European Union", "tax_model": "vat_ioss", "currency": "EUR", "threshold_local": 150.0,
        "basis": "EU IOSS: goods <= EUR 150 have VAT collected by the platform (destination rate ~17%-27%, "
                 "set via --vat-rate); above EUR 150 duty + VAT apply per TARIC classification (not modeled)",
    },
    "sg": {
        "label": "Singapore", "tax_model": "gst", "currency": "SGD", "gst_rate": 0.09,
        "basis": "Singapore import GST 9% (since 2024-01-01) levied on CIF (goods + freight + insurance); "
                 "general goods duty-free (tobacco, alcohol, vehicles, fuel etc. excepted)",
    },
    "other": {
        "label": "Other destinations", "tax_model": "not_modeled", "limit_cny": None,
        "basis": "Destination import tax not modeled; compute per local customs rules (e.g. UK GBP 135, "
                 "Japan duty, Canada GST/PST)",
    },
}


def estimate(price_jpy, channel="ems", domestic_jpy=0.0, rate=None, refresh_rate=True,
             tariff_category=None, tariff_rate=None, destination="cn", vat_rate=None):
    if price_jpy <= 0:
        raise JsbError(f"price_jpy must be positive (got {price_jpy})")
    if domestic_jpy < 0:
        raise JsbError(f"domestic_jpy cannot be negative (got {domestic_jpy})")
    ch = FORWARDING.get(channel)
    if not ch:
        raise JsbError(f"Unknown forwarding lane: {channel} (choose from {', '.join(FORWARDING)})")
    if destination not in DESTINATIONS:
        raise JsbError(f"Unknown destination: {destination} (choose from {', '.join(DESTINATIONS)})")
    if tariff_rate is not None and not 0 <= tariff_rate <= 1:
        raise JsbError(f"tariff_rate must be within 0-1 (got {tariff_rate})")
    if vat_rate is not None and not 0 <= vat_rate <= 1:
        raise JsbError(f"vat_rate must be within 0-1 (got {vat_rate})")
    if tariff_category and tariff_category not in TARIFF_PRESETS:
        raise JsbError(f"Unknown postal-tax category: {tariff_category}"
                       f" (choose from {', '.join(TARIFF_PRESETS)})")

    if rate is None:
        if refresh_rate:
            r = exchange_rate.fetch()  # live refresh; falls back to built-in baseline on network failure
            rate, rate_source = r["rate"], r["source"]
        else:
            rate, rate_source = DEFAULT_RATE, "builtin_baseline"
    else:
        rate_source = "manual"

    price_jpy = float(price_jpy)
    domestic_jpy = float(domestic_jpy)
    item_cny = price_jpy * rate
    domestic_cny = domestic_jpy * rate
    ship_min, ship_max = ch["range"]
    ship_cny = (ship_min * rate, ship_max * rate)
    fee_cny = (HANDLING_FEE[0] * rate, HANDLING_FEE[1] * rate)

    dest = DESTINATIONS[destination]
    local_fx = (exchange_rate.fetch(dest["currency"])
                if dest.get("currency") and refresh_rate
                else {"rate": None, "source": "unavailable"})

    # Import tax: CN fully modeled; HK/SG/US/EU per own rules (missing FX or VAT rate => explicitly marked not-modeled, never invented)
    cif_min = item_cny + domestic_cny + ship_cny[0]   # duty/VAT/GST usually levied on CIF (lower freight bound)
    if destination == "cn":
        if tariff_rate is not None:
            tr, tr_source, tr_label = float(tariff_rate), "manual", "manual override"
        elif tariff_category:
            preset = TARIFF_PRESETS[tariff_category]
            tr, tr_source, tr_label = preset["rate"], tariff_category, preset["label"]
        else:
            tr, tr_source, tr_label = DEFAULT_TARIFF_RATE, "default", "no category given (band 2 default)"
        tariff_raw = item_cny * tr
        tariff_exempt = tariff_raw <= TARIFF_EXEMPT_THRESHOLD
        tariff_cny = 0.0 if tariff_exempt else tariff_raw
        tax_modeled = True
    elif destination == "hk":
        tr, tr_source, tr_label = 0.0, "destination_hk", "HK free port (0% duty & VAT on general goods)"
        tariff_raw = tariff_cny = 0.0
        tariff_exempt = False
        tax_modeled = True
    elif destination == "sg":
        tr, tr_source, tr_label = 0.09, "destination_sg", "GST 9% (on CIF)"
        tariff_raw = tariff_cny = cif_min * 0.09
        tariff_exempt = False
        tax_modeled = True
    elif destination == "us":
        usd_rate = local_fx.get("rate")
        if not usd_rate:
            tr, tr_source = 0.0, "destination_us_fx_missing"
            tr_label = "USD 800 de minimis conversion unavailable (JPY->USD rate missing)"
            tariff_raw = tariff_cny = 0.0
            tax_modeled = False
        else:
            value_usd = (price_jpy + domestic_jpy) * usd_rate
            if value_usd <= 800:
                tr, tr_source = 0.0, "destination_us"
                tr_label = f"within USD 800 de minimis (declared ~${value_usd:,.0f}; state sales tax not modeled)"
                tax_modeled = True
            else:
                tr, tr_source = 0.0, "destination_us"
                tr_label = f"exceeds USD 800 de minimis (~${value_usd:,.0f}); duty per HTS classification not modeled"
                tax_modeled = False
            tariff_raw = tariff_cny = 0.0
        tariff_exempt = False
    elif destination == "eu":
        eur_rate = local_fx.get("rate")
        value_eur = (price_jpy + domestic_jpy) * eur_rate if eur_rate else None
        if vat_rate is None:
            tr, tr_source = 0.0, "destination_eu_vat_missing"
            tr_label = "destination VAT rate required via --vat-rate (17%-27%)"
            tariff_raw = tariff_cny = 0.0
            tax_modeled = False
        elif not value_eur:
            tr, tr_source = 0.0, "destination_eu_fx_missing"
            tr_label = "EUR 150 threshold conversion unavailable (JPY->EUR rate missing)"
            tariff_raw = tariff_cny = 0.0
            tax_modeled = False
        elif value_eur <= 150:
            tr, tr_source = float(vat_rate), "destination_eu"
            tr_label = f"VAT {vat_rate:.0%} (IOSS, goods ~EUR {value_eur:,.0f}, <= 150)"
            tariff_raw = tariff_cny = cif_min * tr
            tax_modeled = True
        else:
            tr, tr_source = 0.0, "destination_eu"
            tr_label = f"exceeds EUR 150 (~EUR {value_eur:,.0f}); duty + VAT per TARIC not modeled"
            tariff_raw = tariff_cny = 0.0
            tax_modeled = False
        tariff_exempt = False
    else:
        tr, tr_source, tr_label = 0.0, "destination_other", "destination import tax not modeled"
        tariff_raw = tariff_cny = 0.0
        tariff_exempt = False
        tax_modeled = False

    total_min = item_cny + domestic_cny + ship_cny[0] + fee_cny[0] + tariff_cny
    total_max = item_cny + domestic_cny + ship_cny[1] + fee_cny[1] + tariff_cny
    snapshot = datetime.datetime.now().astimezone().isoformat()

    data_sources = [
        {"field": "Item price", "source": "User-provided platform page/screenshot (model-recognized, not scraped)"},
        {"field": "Exchange rate", "source": f"scripts/exchange_rate.py (source={rate_source}, snapshot {snapshot})"},
        {"field": "Forwarding fee/handling", "source": "references/forwarding_rates.md (Tsusso Japan China-lane rate range, estimate)"},
        {"field": "Market prices", "source": "scripts/rakuten_search.py (Rakuten RWS) / scripts/amazon_jp_snapshot.py (Amazon JP snapshot); "
                                             "only status=current quotes may be cited"},
        {"field": "Import tax", "source": (f"{dest['basis']}; applicable: {tr_label}" if tax_modeled else dest["basis"])},
    ]
    if dest.get("currency"):
        data_sources.append({
            "field": f"Threshold conversion (JPY->{dest['currency']})",
            "source": f"scripts/exchange_rate.py fetch(target='{dest['currency']}')"
                      + (f", source {local_fx.get('source')}" if local_fx.get("rate") else " (FX unavailable, threshold check skipped)"),
        })

    return {
        "item": {"price_jpy": price_jpy, "domestic_jpy": domestic_jpy},
        "channel": {"key": channel, "label": ch["label"], "days": ch["days"],
                    "note": ch["note"], "jp": list(ch["range"])},
        "destination": {"key": destination, "label": dest["label"],
                        "tax_model": dest["tax_model"], "tax_modeled": tax_modeled,
                        "limit_cny": dest.get("limit_cny"),
                        "threshold_local": dest.get("threshold_local"),
                        "currency": dest.get("currency"), "basis": dest["basis"]},
        "rate": {"jpy_cny": round(rate, 6), "source": rate_source, "snapshot_time": snapshot},
        "tariff": {"rate": tr, "source": tr_source, "category": tr_label,
                   "raw_cny": round(tariff_raw, 2), "exempt": tariff_exempt,
                   "charged_cny": round(tariff_cny, 2),
                   "exempt_threshold": TARIFF_EXEMPT_THRESHOLD, "modeled": tax_modeled},
        "breakdown_cny": {
            "item": round(item_cny, 2),
            "domestic": round(domestic_cny, 2),
            "forwarding": (round(ship_cny[0], 2), round(ship_cny[1], 2)),
            "handling_fee": (round(fee_cny[0], 2), round(fee_cny[1], 2)),
            "tariff": round(tariff_cny, 2),
        },
        "total_cny": (round(total_min, 2), round(total_max, 2)),
        "data_sources": data_sources,
        "estimate_note": "Estimate: subject to live FX / forwarding rates / customs assessment; refresh before purchase.",
        "provenance": {
            "computed_by": "scripts/arrival_price.py",
            "rate_by": "scripts/exchange_rate.py",
            "rule": "All amounts here are computed by scripts; the model must never estimate or alter numbers (provenance constraint).",
        },
    }


FIXED_CAVEATS = [
    "Condition is inferred by recognition, not verified",
    "Used/coupon prices are conditional, not regular prices",
    "FX is a snapshot; refresh before purchase",
    "Forwarding fee varies with actual weight; range shown",
    "Channel coverage is limited; uncovered channels may quote lower",
]


def build_quote_md(res, item_name="", platform="", condition="", confidence="",
                   caveats=None, quote_type="purchase"):
    """Render the estimate into a full confirmation-sheet Markdown (all numbers come from scripts; the model only relays)."""
    b = res["breakdown_cny"]
    r = res["rate"]
    ch = res["channel"]
    t = res["tariff"]
    dest = res["destination"]
    title = "Purchase Confirmation Sheet (estimate)" if quote_type == "purchase" else "Payment Confirmation Sheet (estimate)"
    lines = [f"# {title}", ""]

    if item_name:
        lines.append(f"**Item**: {item_name}")
    if platform:
        lines.append(f"**Platform/channel**: {platform}")
    if condition:
        lines.append(f"**Condition**: {condition} (inferred by recognition, to be verified)")
    if confidence:
        lines.append(f"**Match confidence**: {confidence}")
    lines.append(f"**Ship-to**: {dest['label']} (tax model: {dest['tax_model']})")
    lines.append("")

    if dest["key"] == "cn":
        if t["exempt"]:
            tax_cell = f"{t['rate']:.0%} | {t['category']}"
            tax_extra = f" (due {t['raw_cny']:,.2f} <= {t['exempt_threshold']:.0f} CNY, exempt)"
        else:
            tax_cell = f"{t['rate']:.0%} | {t['category']}"
            tax_extra = ""
        tax_label = "Postal import tax"
    elif dest["key"] == "hk":
        tax_cell, tax_extra, tax_label = "0% (HK free port)", "", "Import tax"
    elif dest["key"] == "sg":
        tax_cell, tax_extra, tax_label = "9% (on CIF)", "", "GST"
    elif dest["key"] == "us":
        tax_cell, tax_extra, tax_label = t["category"], "", "Customs duty"
    elif dest["key"] == "eu":
        if t["modeled"]:
            tax_cell, tax_extra, tax_label = f"{t['rate']:.0%} (on CIF)", "", "VAT"
        else:
            tax_cell, tax_extra, tax_label = "not modeled", " (requires --vat-rate or FX threshold conversion)", "VAT"
    else:
        tax_cell, tax_extra, tax_label = "not modeled", " (compute per destination tax rules)", "Import tax"

    lines += [
        f"**Landed-cost breakdown (estimate; FX snapshot {r['snapshot_time']}, JPY->CNY {r['jpy_cny']}, source {r['source']})**",
        "",
        "| Line item | Amount (CNY) |",
        "|---|---|",
        f"| Item price (JPY {res['item']['price_jpy']:,.0f}) | {b['item']:,.2f} |",
        f"| Japan domestic shipping (JPY {res['item']['domestic_jpy']:,.0f}) | {b['domestic']:,.2f} |",
        f"| Forwarding shipping ({ch['label']}, {ch['days']}) | {b['forwarding'][0]:,.2f} ~ {b['forwarding'][1]:,.2f} |",
        f"| Forwarding handling fee | {b['handling_fee'][0]:,.2f} ~ {b['handling_fee'][1]:,.2f} |",
        f"| {tax_label} ({tax_cell}) | {b['tariff']:,.2f}{tax_extra} |",
        f"| **Total (estimate)** | **{res['total_cny'][0]:,.2f} ~ {res['total_cny'][1]:,.2f}** |",
        "",
        "**Caveats (must read)**",
        "",
    ]
    for c in FIXED_CAVEATS + list(caveats or []):
        lines.append(f"- {c}")

    lines += [
        "",
        "**Calculation basis & data sources**",
        "",
        "| Line item | Basis / source |",
        "|---|---|",
    ]
    for s in res["data_sources"]:
        lines.append(f"| {s['field']} | {s['source']} |")
    lines += [
        "",
        "**Estimate disclaimer**: amounts computed by `scripts/arrival_price.py`, FX by `scripts/exchange_rate.py`; "
        "the model did not compute any number. Subject to live FX / forwarding rates / customs assessment.",
        "",
        "- [ ] User confirms item & amounts",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Japan-shopping landed-cost estimate")
    ap.add_argument("--price-jpy", type=float, required=True, help="item price (tax-incl., JPY)")
    ap.add_argument("--domestic-jpy", type=float, default=0, help="Japan domestic shipping (JPY, default 0)")
    ap.add_argument("--channel", default="ems", choices=list(FORWARDING))
    ap.add_argument("--rate", type=float, default=None, help="manual FX rate JPY->CNY")
    ap.add_argument("--baseline", action="store_true", help="use built-in baseline FX, no network")
    ap.add_argument("--quote", action="store_true", help="also render the full confirmation sheet (Markdown)")
    ap.add_argument("--quote-file", default=None, help="file path for the sheet (with --quote)")
    ap.add_argument("--quote-type", default="purchase", choices=["purchase", "payment"],
                    help="purchase=neutral sheet; payment=PayPal-flavored sheet")
    ap.add_argument("--item-name", default="", help="item name (into the sheet)")
    ap.add_argument("--platform", default="", help="platform/channel (into the sheet)")
    ap.add_argument("--condition", default="", help="condition (into the sheet)")
    ap.add_argument("--confidence", default="", help="same-item match confidence: High/Medium/Low")
    ap.add_argument("--caveats", action="append", default=[], help="append a caveat (repeatable)")
    ap.add_argument("--weight-kg", type=float, default=None,
                    help="declared weight (kg). Built-in rate table covers <=1.5kg parcels; overweight triggers a warning")
    ap.add_argument("--tariff-category", default=None, choices=list(TARIFF_PRESETS),
                    help="official postal-tax band rate (it/toy/furniture/sports/food/precious_metal=13%%, "
                         "textile/appliance/bike/other=20%%, luxury/jewelry/golf/tobacco_alcohol=50%%)")
    ap.add_argument("--tariff-rate", type=float, default=None,
                    help="manual postal-tax rate (0-1, overrides category; only with --destination cn)")
    ap.add_argument("--destination", default="cn", choices=list(DESTINATIONS),
                    help="ship-to: cn=Mainland China (personal postal, fully modeled) / hk=HK free port / "
                         "us=US USD 800 de minimis / eu=EU IOSS (needs --vat-rate) / sg=Singapore GST 9%% / other=not modeled")
    ap.add_argument("--vat-rate", type=float, default=None,
                    help="EU destination VAT rate (0-1, e.g. Germany 0.19, France 0.20); only with --destination eu")
    args = ap.parse_args()

    try:
        result = estimate(args.price_jpy, channel=args.channel,
                          domestic_jpy=args.domestic_jpy, rate=args.rate,
                          refresh_rate=not args.baseline,
                          tariff_category=args.tariff_category,
                          tariff_rate=args.tariff_rate,
                          destination=args.destination,
                          vat_rate=args.vat_rate)
    except JsbError as e:
        print(json.dumps({"status": "error", "code": "BAD_INPUT", "error": str(e)},
                         ensure_ascii=False, indent=2))
        raise SystemExit(1)

    result["status"] = "current"
    if args.weight_kg is not None:
        result["weight_kg"] = args.weight_kg
        if args.weight_kg > 1.5:
            result["weight_warning"] = (
                f"Declared weight {args.weight_kg}kg exceeds the built-in rate-table scope (<=1.5kg parcels): "
                "the forwarding range below uses small-parcel rates; for heavy items (appliances/furniture) "
                "check Tsusso Japan live quotes.")
            args.caveats.append(result["weight_warning"])
    item_cny = result["breakdown_cny"]["item"]
    if args.destination == "cn" and item_cny > POSTAL_LIMIT_CNY:
        result["postal_limit"] = {"item_cny": item_cny, "limit_cny": POSTAL_LIMIT_CNY,
                                  "exceeded": True}
        args.caveats.append(
            f"Item price ~= {item_cny:,.2f} CNY exceeds the personal postal per-parcel limit "
            f"{POSTAL_LIMIT_CNY:,.0f} CNY (800 for HK/MO/TW): this order cannot clear customs as a personal parcel; "
            "split the shipment, return it, or use cross-border e-commerce retail import (5000 CNY per-order limit, "
            "~9.1% composite rate) / formal cargo declaration. The postal tax below is reference only.")
    if args.destination != "cn":
        args.caveats.append(
            "Forwarding rates come from Tsusso Japan China lanes; other destinations may have different lanes "
            "and prices. Where import tax is not modeled, compute per destination customs rules.")
    if args.quote:
        result["quote_md"] = build_quote_md(
            result, item_name=args.item_name, platform=args.platform,
            condition=args.condition, confidence=args.confidence,
            caveats=args.caveats, quote_type=args.quote_type,
        )
        if args.quote_file:
            with open(args.quote_file, "w", encoding="utf-8") as f:
                f.write(result["quote_md"])
            result["quote_file"] = args.quote_file

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
