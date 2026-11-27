"""Storefront shipping rates for parcels dispatched from PIN 635126."""

from decimal import Decimal, ROUND_HALF_UP
import re


ORIGIN_PIN = "635126"
ITEM_WEIGHT_GRAMS = 450
FREE_SHIPPING_THRESHOLD = Decimal("4599")
METRO_PREFIXES = {"110", "400", "500", "560", "600", "700"}
RATES = {
    "local": (40, 55, 15),
    "state": (55, 75, 20),
    "metro": (82, 105, 30),
    "rest": (90, 143, 47),
    "remote": (90, 143, 47),
}


def shipping_charge(pincode, item_count, merchandise_total):
    pin = (pincode or "").strip()
    if not re.fullmatch(r"[1-9][0-9]{5}", pin):
        raise ValueError("Enter a valid six-digit shipping PIN code.")
    if merchandise_total >= FREE_SHIPPING_THRESHOLD:
        return Decimal("0")

    prefix = pin[:3]
    if prefix == ORIGIN_PIN[:3]:
        zone = "local"
    elif pin[:2] in {"60", "61", "62", "63", "64"}:
        zone = "state"
    elif prefix in METRO_PREFIXES:
        zone = "metro"
    elif pin[:2] in {"18", "19", "79"} or prefix == "744":
        zone = "remote"
    else:
        zone = "rest"

    first, second, extra = RATES[zone]
    weight = item_count * ITEM_WEIGHT_GRAMS
    extra_slabs = max(0, (weight - 1000 + 499) // 500)
    base = first if weight <= 500 else second + extra_slabs * extra
    return (Decimal(base) * Decimal("1.18")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
