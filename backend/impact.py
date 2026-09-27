"""Waste-prevention indicators derived from recorded cooking, not assumed prices.

An ingredient counts as *saved* when a completed meal used it within the
"use soon" window (0-5 days before its recorded expiry) -- the same window the
home screen uses to ask the user to cook it. Weight and CO2e are estimates:
weight comes from the recorded amount when it has a mass/volume unit and from
typical portion weights otherwise; CO2e uses a conservative average factor for
avoided household food waste.
"""
import json
import re
from datetime import date, datetime, timedelta, timezone

RESCUE_WINDOW_DAYS = 5
# Conservative average emissions avoided per kg of household food not wasted
# (published estimates for the UK/EU range from about 2.5 to 4 kg CO2e per kg).
CO2E_KG_PER_KG_FOOD = 2.5

# Typical weight of one "piece"/portion when the amount has no mass unit.
TYPICAL_GRAMS = [
    (r"egg", 55), (r"berr|grape|cherr", 125), (r"banana", 120), (r"apple|orange|pear|peach", 150),
    (r"lemon|lime|kiwi", 80), (r"avocado", 170), (r"watermelon|melon", 900), (r"potato", 170),
    (r"onion|pepper|tomato|cucumber|carrot|eggplant|zucchini", 130), (r"garlic", 5),
    (r"lettuce|cabbage|broccoli|cauliflower", 400), (r"spinach|kale|herb|basil|parsley|cilantro", 60),
    (r"chicken|beef|pork|lamb|turkey|steak|sirloin|mince", 250), (r"shrimp|fish|salmon|tuna|cod", 200),
    (r"milk|cream|yogurt", 250), (r"cheese|brie|feta", 100), (r"bread|baguette", 250), (r"rice|pasta|noodle", 90),
]
UNIT_GRAMS = {"g": 1, "gram": 1, "grams": 1, "kg": 1000, "ml": 1, "l": 1000, "litre": 1000, "liter": 1000}


def estimate_grams(item: dict) -> int:
    """Estimated mass of the ingredient used, in grams."""
    text = f"{item.get('quantity_used', '')}"
    match = re.match(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?", text)
    if match and (match.group(2) or "").lower() in UNIT_GRAMS:
        return round(float(match.group(1)) * UNIT_GRAMS[match.group(2).lower()])
    amount = item.get("recipe_amount") or item.get("amount_used") or 1
    unit = str(item.get("recipe_unit") or "").lower()
    if unit in UNIT_GRAMS:
        return round(float(amount) * UNIT_GRAMS[unit])
    name = str(item.get("ingredient", "")).lower()
    per_piece = next((grams for pattern, grams in TYPICAL_GRAMS if re.search(pattern, name)), 120)
    pieces = float(amount) if unit in {"", "piece", "pieces", "portion", "whole", "cup", "cups", "serving"} else 1
    return round(min(max(pieces, 0.25), 6) * per_piece)


def _days_left(expiry: str | None, today: date) -> int | None:
    try:
        return (datetime.fromisoformat(str(expiry)).date() - today).days
    except (TypeError, ValueError):
        return None


def cooking_impact(sessions, recipe_titles, now=None, pantry_items=None):
    now = (now or datetime.now(timezone.utc)).astimezone()
    week_start = (now - timedelta(days=now.weekday())).date()
    completed = sorted((s for s in sessions if s.status == "completed"), key=lambda s: s.id, reverse=True)
    used, rescued, weekly, grams = 0, 0, 0, 0
    counts, events = {}, []
    weeks = {week_start - timedelta(weeks=offset): 0 for offset in range(7, -1, -1)}
    for session in completed:
        try:
            # Local dates, like the "Use soon" panel (UTC is a day behind in UTC+8 until 8 am).
            started = datetime.fromisoformat(session.started_at.replace("Z", "+00:00")).astimezone()
            snapshot = json.loads(session.pantry_snapshot or "[]")
        except (ValueError, TypeError):
            continue
        weekly += int(week_start <= started.date() <= now.date())
        if not isinstance(snapshot, list):
            continue
        for item in snapshot:
            if not isinstance(item, dict) or not item.get("ingredient"):
                continue
            if item.get("deducted", True) and "amount_used" in item and item["amount_used"] is not None and (
                not isinstance(item["amount_used"], (int, float)) or item["amount_used"] <= 0
            ):
                continue
            ingredient = str(item["ingredient"]).strip().lower()
            used += 1
            counts[ingredient] = counts.get(ingredient, 0) + 1
            days = _days_left(item.get("expiry_date"), started.date())
            if days is None or not 0 <= days <= RESCUE_WINDOW_DAYS:
                continue
            rescued += 1
            item_grams = estimate_grams(item)
            grams += item_grams
            session_week = started.date() - timedelta(days=started.weekday())
            if session_week in weeks:
                weeks[session_week] += 1
            events.append({"session_id": session.id, "ingredient": ingredient,
                           "recipe_title": recipe_titles.get(session.recipe_id, "Completed meal"),
                           "quantity_used": item.get("quantity_used", "Amount not recorded"),
                           "days_to_expiry": days, "expiry_estimated": bool(item.get("expiry_estimated")),
                           "estimated_grams": item_grams, "cooked_at": started.isoformat()})

    at_risk = []
    for pantry_item in pantry_items or []:
        days = _days_left(pantry_item.expiry_date, now.date())
        if days is not None and 0 <= days <= RESCUE_WINDOW_DAYS:
            at_risk.append({"ingredient": pantry_item.ingredient, "days_left": days})
    at_risk.sort(key=lambda entry: entry["days_left"])

    return {
        "meals_cooked": len(completed), "meals_this_week": weekly,
        "last_meal": recipe_titles.get(completed[0].recipe_id) if completed else None,
        "top_ingredient": max(counts, key=counts.get) if counts else None,
        "ingredients_used": used, "rescued_items": rescued,
        "rescue_rate": round(rescued * 100 / used) if used else 0,
        "last_rescue_count": sum(e["session_id"] == completed[0].id for e in events) if completed else 0,
        "rescue_events": events[:20],
        "estimated_grams_saved": grams,
        "estimated_co2e_kg": round(grams / 1000 * CO2E_KG_PER_KG_FOOD, 2),
        "weekly_rescues": [{"week_start": week.isoformat(), "count": count} for week, count in weeks.items()],
        "at_risk_count": len(at_risk), "at_risk_items": at_risk[:8],
        "rescue_window_days": RESCUE_WINDOW_DAYS,
        "metric_basis": (
            f"Pantry foods used in completed meals within {RESCUE_WINDOW_DAYS} days of their recorded expiry. "
            "Weight is estimated from recorded amounts or typical portion sizes; CO2e uses "
            f"{CO2E_KG_PER_KG_FOOD} kg CO2e per kg of food not wasted. Estimates, not measured disposal."
        ),
    }
