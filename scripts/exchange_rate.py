# -*- coding: utf-8 -*-
"""FX lookup: JPY->CNY (any target currency for US/EU de-minimis threshold conversion).

Primary open.er-api.com/v6 (keyless) -> backup exchangerate-api.com/v4 -> local cache -> built-in baseline (CNY only).
Usage:
  python3 exchange_rate.py
  python3 exchange_rate.py --to USD        # JPY->USD (US USD 800 de minimis conversion)
  python3 exchange_rate.py --baseline      # built-in baseline only, no network (CNY only)
"""
import argparse
import json
import os

from _common import http_request, JsbError

FALLBACK_RATE = 0.04224  # measured baseline (k780), JPY->CNY only

SOURCES = [
    ("open.er-api.com/v6", "https://open.er-api.com/v6/latest/JPY", "rates"),
    ("exchangerate-api.com/v4", "https://api.exchangerate-api.com/v4/latest/JPY", "rates"),
]


def _cache_file(target):
    base = os.environ.get("JSB_CACHE_DIR", os.path.expanduser("~/.japan-shopping-buddy"))
    return os.path.join(base, f"exchange_rate_{target}.json")


def _read_cache(target):
    try:
        with open(_cache_file(target), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(record, target):
    try:
        os.makedirs(os.path.dirname(_cache_file(target)), exist_ok=True)
        with open(_cache_file(target), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def fetch(target="CNY"):
    """Query JPY->target FX; degrades to cache/baseline on network failure, never throws."""
    errors = []
    for source, url, rates_key in SOURCES:
        try:
            # FX APIs are global CDNs; no Japan proxy needed, direct is fine
            status, text = http_request("GET", url, use_proxy=False, timeout=12)
            if status == 200:
                data = json.loads(text)
                rate = data.get(rates_key, {}).get(target)
                if rate:
                    return {
                        "base": "JPY",
                        "target": target,
                        "rate": float(rate),
                        "source": source,
                        "time_utc": data.get("time_last_update_utc") or data.get("date"),
                        "is_fallback": False,
                    }
            errors.append(f"{source} -> HTTP {status}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{source} -> {e}")

    cached = _read_cache(target)
    if cached and cached.get("rate"):
        cached["is_fallback"] = True
        cached["fallback_reason"] = "network_failed: " + "; ".join(errors)
        return cached

    if target == "CNY":
        return {
            "base": "JPY",
            "target": "CNY",
            "rate": FALLBACK_RATE,
            "source": "builtin_baseline",
            "is_fallback": True,
            "fallback_reason": "network_failed: " + "; ".join(errors),
        }
    # non-CNY has no built-in baseline: return null rate so the caller marks "threshold conversion unavailable" — never invent a number
    return {
        "base": "JPY", "target": target, "rate": None,
        "source": "unavailable", "is_fallback": True,
        "fallback_reason": "network_failed: " + "; ".join(errors),
    }


def main():
    ap = argparse.ArgumentParser(description="Query JPY -> target currency FX rate")
    ap.add_argument("--to", default="CNY", help="target currency (default CNY)")
    ap.add_argument("--baseline", action="store_true", help="built-in baseline only (CNY only)")
    args = ap.parse_args()

    if args.baseline:
        if args.to != "CNY":
            print(json.dumps({"error": "Built-in baseline covers JPY->CNY only", "code": "NO_BASELINE"},
                             ensure_ascii=False, indent=2))
            raise SystemExit(1)
        result = {
            "base": "JPY", "target": "CNY", "rate": FALLBACK_RATE,
            "source": "builtin_baseline", "is_fallback": True,
        }
    else:
        try:
            result = fetch(args.to)
        except JsbError as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
            raise SystemExit(1)
        if not result.get("is_fallback") and result.get("rate"):
            _write_cache(result, args.to)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()