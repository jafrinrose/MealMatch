"""Deterministic receipt-line handling around the language-model step.

Tesseract returns raw lines. This module picks out the purchased-product lines,
reads the quantities a receipt states (repeated lines, "2 @ 1.99", weights and
pack sizes) and expands common receipt abbreviations as hints. The language
model then only names and classifies numbered lines, so it cannot invent items
that are not on the receipt or drop repeated purchases. Finally the answers
are merged into one confirmation row per ingredient and unit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Transaction, payment and store lines: never a product.
NON_ITEM_PATTERN = re.compile(
    r"\b(sub\s*-?total|total|tax|hst|gst|pst|vat|balance|change|cash|visa|mastercard|amex|"
    r"debit|credit|interac|tender|acct|account|auth|approval|approved|reference|ref|invoice|"
    r"terminal|transaction|member|membership|cashier|operator|thank|thanks|customer|copy|retain|"
    r"records|sold|amount|savings|saved|points|rewards|survey|www|http|tel|phone|deposit|fee|"
    r"levy|coupon|discount|card|payment|due)\b",
    re.IGNORECASE,
)
STOP_PATTERN = re.compile(r"^\W*(sub\s*-?\s*total|total|balance)\b", re.IGNORECASE)
# OCR reads a 0 inside numbers as "@" ("@.512 kg", "2@PK"); "3 @ 1.29" keeps its spaces.
OCR_AT_AS_ZERO = re.compile(r"@(?=[.,]\d)|(?<=\d)@(?=[A-Za-z])")
ITEMS_SOLD_PATTERN = re.compile(r"items?\s+sold\s*[=:#-]?\s*(\d{1,3})\b", re.IGNORECASE)
ADDRESS_PATTERN = re.compile(
    r"^\d{1,6}\s+[A-Za-z .'-]+\s(way|st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|hwy|"
    r"highway|lane|ln|pkwy|parkway|court|crescent|cres)\.?$",
    re.IGNORECASE,
)
DATE_TIME_PATTERN = re.compile(r"\d{1,4}[/-]\d{1,2}[/-]\d{2,4}|\b\d{1,2}:\d{2}\b")
MASKED_CARD_PATTERN = re.compile(r"[xX*]{4,}")
# Discounts and refunds ("776059 /ARTISAN BGT 1.00-") would otherwise count as another purchase.
NEGATIVE_PRICE_PATTERN = re.compile(r"(\d[.,]\d{2}-|-\s?\$?\d+[.,]\d{2})\s*[A-Za-z]?\s*$")

# Item codes, optionally after a one-letter tax flag ("E 776059 ARTISAN BGT").
ITEM_CODE_PATTERN = re.compile(r"^\W*(?:[A-Z]\s+)?\d{4,14}\s+")
PRICE_TOKEN = re.compile(r"^[$€£]?\d{1,5}[.,]\d{2}-?$")
# OCR-garbled prices ("g'gg.", "289.", "@.95"), stray punctuation, tax flags and barcodes.
JUNK_TOKEN = re.compile(
    r"^(?:[^A-Za-z0-9]+|[A-Za-z]|\d{5,}|[\dgGoOlIsSbB@'’.,:;]*[.,'’][\dgGoOlIsSbB@'’.,:;]*)$"
)

# Quantities the receipt states.
WEIGHT_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s?(kg|lbs?)\s*@", re.IGNORECASE)
AT_COUNT_PATTERN = re.compile(r"(?<![\d.,])(\d{1,2})\s*@\s*[$€£]?\d+[.,]\d{2}")
LEADING_COUNT_PATTERN = re.compile(r"^(\d{1,2})\s*[xX×]\s+")
TRAILING_COUNT_PATTERN = re.compile(r"\s[xX×]\s?(\d{1,2})\b")
QTY_PATTERN = re.compile(r"\bqty\.?\s*:?\s*(\d{1,3})\b", re.IGNORECASE)
# Single-letter units must touch the number ("4L", "750G") so "4.99 G" tax flags are not sizes.
SIZE_PATTERN = re.compile(
    r"(?<![\d.,/])(\d+(?:[.,]\d+)?)(?:(l|g)|\s?(ml|kg|lbs?|oz|ct|pk|pack|dz|doz|dozen|count))\b",
    re.IGNORECASE,
)
CONTINUATION_WORDS = re.compile(r"\b(kg|lbs?|ea|each|qty|x|@)\b", re.IGNORECASE)

# Common grocery-receipt abbreviations. Used only as hints for the model.
ABBREVIATIONS = {
    "APPL": "apple", "APPLS": "apples", "ASPRGS": "asparagus", "AVO": "avocado", "AVOC": "avocado",
    "B/S": "boneless skinless", "BNLS": "boneless", "SKNLS": "skinless", "BNLS/SKNLS": "boneless skinless",
    "BAGT": "baguette", "BGT": "baguette", "BGTTE": "baguette", "BAN": "banana", "BNNA": "banana",
    "BCN": "bacon", "BF": "beef", "BRD": "bread", "BROC": "broccoli", "BRST": "breast",
    "BRWN": "brown", "BTR": "butter", "BTTR": "butter", "CAULI": "cauliflower", "CHED": "cheddar",
    "CHKN": "chicken", "CKN": "chicken", "CHS": "cheese", "CHSE": "cheese", "CILNTRO": "cilantro",
    "CRM": "cream", "CRMCHS": "cream cheese", "CUC": "cucumber", "CUKE": "cucumber",
    "CRMBL": "crumbled", "DRMSTK": "drumstick", "ENG": "english", "EVOO": "extra virgin olive oil", "FLR": "flour", "FRZ": "frozen",
    "FZN": "frozen", "GRK": "greek", "GRLC": "garlic", "GRD": "ground", "GRND": "ground",
    "GRN": "green", "HVY": "heavy", "KS": "kirkland (brand)", "JC": "juice", "JCE": "juice", "LG": "large", "LRG": "large",
    "LETT": "lettuce", "LTTC": "lettuce", "MLK": "milk", "MOZZ": "mozzarella", "MSHRM": "mushroom",
    "MUSH": "mushroom", "OJ": "orange juice", "OLV": "olives", "OLVS": "olives", "ONN": "onion",
    "ORG": "organic", "PB": "peanut butter", "PNUT": "peanut", "PPR": "pepper", "PEPR": "pepper",
    "PRSDNT": "president (brand)", "ROM": "romaine", "SAUS": "sausage", "SHRD": "shredded",
    "SKM": "skim", "SLMN": "salmon", "SPGHTI": "spaghetti", "SR": "sour", "STRAWB": "strawberries",
    "STRAWBRY": "strawberries", "STRWBRY": "strawberries", "SWT": "sweet", "THGH": "thigh", "TIN": "canned",
    "THGHS": "thighs", "TKY": "turkey", "TRKY": "turkey", "TOM": "tomato", "TOMS": "tomatoes",
    "VEG": "vegetable", "WHL": "whole", "WHIP": "whipping", "WHP": "whipping", "WTR": "water", "YGT": "yogurt",
    "YGRT": "yogurt", "YOG": "yogurt", "ZUCC": "zucchini",
    # Non-food, so the model sees what the line really is.
    "BATT": "batteries", "BTRY": "battery", "DET": "detergent", "DETG": "detergent",
    "SHMP": "shampoo", "TISS": "tissue", "TWL": "towel", "TWLS": "towels",
}
# Words receipts spell out in full, used to expand vowel-less abbreviations such
# as BRKFST, CHDR or BBY that are not in the table above.
GROCERY_WORDS = set("""
apple apricot avocado banana berry blackberry blueberry cantaloupe cherry clementine coconut
cranberry date fig grape grapefruit kiwi lemon lime mandarin mango melon nectarine orange papaya
peach pear pineapple plum pomegranate raspberry strawberry tangerine watermelon artichoke arugula
asparagus basil bean beet beetroot broccoli brussels cabbage carrot cauliflower celery chard chili
chive cilantro coriander corn courgette cucumber dill eggplant fennel garlic ginger herb kale leek
lettuce mint mushroom okra onion parsley parsnip pea pepper potato pumpkin radish rocket romaine
rosemary sage salad scallion shallot spinach sprout squash thyme tomato turnip vegetable yam
zucchini bacon beef breast brisket burger chicken chop cod crab drumstick duck fillet fish haddock
ham lamb lobster meatball mince mussel pork prawn salami salmon sardine sausage scallop shrimp
sirloin steak thigh tilapia trout tuna turkey wing chorizo pepperoni prosciutto butter buttermilk
brie camembert cheddar cheese cottage cream creamer custard egg feta gouda halloumi kefir margarine
mascarpone milk mozzarella parmesan provolone ricotta yogurt bagel baguette bread brioche bun cake
cereal ciabatta cookie couscous cracker croissant flour granola loaf macaroni muffin noodle oat
oatmeal pancake pasta penne pita quinoa rice roll sourdough spaghetti tortilla waffle wrap rye
almond broth cashew chickpea chocolate cinnamon cocoa coffee honey hummus jam juice ketchup lentil
maple mayonnaise mustard nut oil olive paprika peanut pecan pesto pickle popcorn raisin salsa salt
sauce seed soda soup soy spice stock sugar syrup tea vanilla vinegar walnut water yeast sesame
tahini pretzel chip crisp baby breakfast boneless skinless brown white whole skim skimmed semi
sweet sparkling smoked shredded sliced grated ground frozen canned dried dry fresh organic large
small medium jumbo lean extra virgin unsalted salted mild mature sharp greek italian english
french plain original natural green red yellow black low fat reduced light heavy double single
free range mini roma russet gala jasmine basmati kalamata crumbled chopped diced minced instant
rolled mixed seedless unsweetened sweetened loose family
""".split())
VOWELS = set("aeiou")

# Letters Tesseract confuses on thermal receipts ("OLV" read as "OLY").
OCR_CONFUSIONS = {"Y": "V", "V": "Y", "0": "O", "O": "0", "1": "IT", "I": "1LT", "L": "I", "5": "S", "S": "5", "8": "B", "B": "8"}

PLURAL_UNITS = {"piece": "pieces", "pack": "packs", "bag": "bags", "box": "boxes", "carton": "cartons",
                "bottle": "bottles", "can": "cans", "jar": "jars", "bunch": "bunches"}
# Receipt size unit -> (confirmation-screen unit, factor).
SIZE_UNITS = {"l": ("l", 1), "ml": ("ml", 1), "g": ("g", 1), "kg": ("kg", 1), "lb": ("kg", 0.4536),
              "lbs": ("kg", 0.4536), "oz": ("g", 28.35), "ct": ("piece", 1), "pk": ("piece", 1),
              "pack": ("piece", 1), "count": ("piece", 1), "dz": ("piece", 12), "doz": ("piece", 12),
              "dozen": ("piece", 12)}


@dataclass
class ReceiptLine:
    number: int
    text: str
    raw: list[str] = field(default_factory=list)
    count: int = 1
    size: tuple[float, str] | None = None  # per unit, e.g. (4, "l") or (12, "piece")
    weight: float | None = None  # kilograms bought, for weighed produce

    @property
    def hint(self) -> str:
        expanded = expand_abbreviations(self.text)
        return expanded if expanded != self.text.lower() else ""


def expand_abbreviations(text: str) -> str:
    words = []
    for token in text.split():
        key = token.upper().strip(".,:;")
        expansion = ABBREVIATIONS.get(key)
        if expansion is None and len(key) >= 3:
            variants = (
                key[:index] + swap + key[index + 1:]
                for index, letter in enumerate(key)
                for swap in OCR_CONFUSIONS.get(letter, "")
            )
            expansion = next((ABBREVIATIONS[variant] for variant in variants if variant in ABBREVIATIONS), None)
        words.append(expansion or _expand_vowelless(key) or token.lower())
    return " ".join(words)


def _skeleton(word: str) -> str:
    """Consonants in order, doubled letters collapsed: "cheddar" -> "chdr"."""
    consonants = [letter for letter in word if letter not in VOWELS]
    return "".join(letter for index, letter in enumerate(consonants) if index == 0 or letter != consonants[index - 1])


def _is_subsequence(short: str, long: str) -> bool:
    letters = iter(long)
    return all(letter in letters for letter in short)


def _expand_vowelless(token: str) -> str | None:
    """
    Receipt abbreviations mostly drop vowels (BRKFST, CHDR, BBY). A token with no
    vowels at all is almost never a real word, so it is matched to the grocery
    word that keeps most of its consonants. Ties are left for the model.
    """

    token = token.lower()
    if len(token) < 3 or not token.isalpha() or VOWELS & set(token) or token in GROCERY_WORDS:
        return None
    skeleton = _skeleton(token)
    scored = []
    for word in GROCERY_WORDS | {value for value in ABBREVIATIONS.values() if value.isalpha()}:
        word_skeleton = _skeleton(word)
        if word[0] == token[0] and _is_subsequence(token, word) and _is_subsequence(skeleton, word_skeleton):
            coverage = len(skeleton) / len(word_skeleton)
            if coverage >= 0.75:
                scored.append((coverage, -len(word), word))
    scored.sort(reverse=True)
    if not scored or (len(scored) > 1 and scored[0][:2] == scored[1][:2]):
        return None
    return scored[0][2]


def _stated_count(text: str) -> tuple[int | None, str]:
    for pattern in (AT_COUNT_PATTERN, LEADING_COUNT_PATTERN, TRAILING_COUNT_PATTERN, QTY_PATTERN):
        match = pattern.search(text)
        if match and int(match.group(1)) > 0:
            return int(match.group(1)), text[: match.start()] + " " + text[match.end():]
    return None, text


def _stated_weight(text: str) -> tuple[float | None, str]:
    match = WEIGHT_PATTERN.search(text)
    if not match:
        return None, text
    amount = float(match.group(1).replace(",", "."))
    kilograms = amount if match.group(2).lower() == "kg" else amount * 0.4536
    # Drop the "@ 1.52/kg" unit price that follows the weight.
    rest = re.sub(r"^\s*[$€£]?\d+[.,]\d{2}\s*/\s*(kg|lbs?)", "", text[match.end():], flags=re.IGNORECASE)
    return kilograms, text[: match.start()] + " " + rest


def _stated_size(text: str) -> tuple[tuple[float, str] | None, str]:
    match = SIZE_PATTERN.search(text)
    if not match:
        return None, text
    unit, factor = SIZE_UNITS[(match.group(2) or match.group(3)).lower()]
    return (float(match.group(1).replace(",", ".")) * factor, unit), text[: match.start()] + " " + text[match.end():]


def _strip_price_and_junk(text: str) -> tuple[str, bool]:
    tokens = text.split()
    had_price = False
    while tokens and (PRICE_TOKEN.match(tokens[-1]) or JUNK_TOKEN.match(tokens[-1])):
        had_price = had_price or bool(PRICE_TOKEN.match(tokens[-1]) or re.search(r"[.,]\d|\d[.,]|[.,']$", tokens[-1]))
        tokens.pop()
    while tokens and re.match(r"^[^A-Za-z0-9/]+$", tokens[0]):
        tokens.pop(0)
    return " ".join(tokens), had_price


def _is_continuation(text: str) -> bool:
    """A line such as "2 @ 1.49" or "1.240 kg @ $1.52/kg 1.88" that belongs to the item above."""
    if not (AT_COUNT_PATTERN.search(text) or WEIGHT_PATTERN.search(text) or QTY_PATTERN.search(text)):
        return False
    return not re.search(r"[A-Za-z]{2,}", CONTINUATION_WORDS.sub(" ", text))


def items_sold(raw_lines: list[str]) -> int | None:
    for line in raw_lines:
        match = ITEMS_SOLD_PATTERN.search(line)
        if match:
            return int(match.group(1))
    return None


def parse_receipt_lines(raw_lines: list[str]) -> list[ReceiptLine]:
    """Return one ReceiptLine per distinct product description, with repeats counted."""
    parsed: list[dict] = []
    for raw in raw_lines:
        line = OCR_AT_AS_ZERO.sub("0", raw.strip())
        if parsed and STOP_PATTERN.search(line):
            break
        if _is_continuation(line):
            if parsed:
                target = parsed[-1]
                weight, _ = _stated_weight(line)
                count, _ = _stated_count(line)
                if weight:
                    target["weight"] = weight
                elif count:
                    target["count"] = count
                target["priced"] = True
            continue
        if (
            not re.search(r"[A-Za-z]{2,}", line)
            or NON_ITEM_PATTERN.search(line)
            or ADDRESS_PATTERN.match(line)
            or DATE_TIME_PATTERN.search(line)
            or MASKED_CARD_PATTERN.search(line)
            or NEGATIVE_PRICE_PATTERN.search(line)
        ):
            continue
        has_code = bool(ITEM_CODE_PATTERN.match(line))
        text = ITEM_CODE_PATTERN.sub("", line)
        weight, text = _stated_weight(text)
        count, text = _stated_count(text)
        size, text = _stated_size(text)
        text, had_price = _strip_price_and_junk(text)
        text = re.sub(r"\s+", " ", text).strip(" -—–=|:;,")
        if len(re.sub(r"[^A-Za-z]", "", text)) < 3:
            continue
        parsed.append({"text": text, "raw": line, "count": count or 1, "size": size, "weight": weight,
                       "priced": had_price or has_code or bool(weight or count)})

    # When most lines carry a price or item code, the unpriced ones are headers
    # (store name, city). Otherwise OCR lost the prices and every line is kept.
    if sum(1 for item in parsed if item["priced"]) >= 2:
        parsed = [item for item in parsed if item["priced"]]

    grouped: dict[tuple, ReceiptLine] = {}
    for item in parsed:
        key = (re.sub(r"[^A-Z0-9]+", " ", item["text"].upper()).strip(), item["size"])
        line = grouped.get(key)
        if line is None:
            grouped[key] = ReceiptLine(len(grouped) + 1, item["text"], [item["raw"]], item["count"], item["size"], item["weight"])
            continue
        line.raw.append(item["raw"])
        line.count += item["count"]
        if item["weight"]:
            line.weight = (line.weight or 0) + item["weight"]
    return list(grouped.values())


def format_quantity(amount: float, unit: str) -> str:
    amount = round(amount, 2)
    shown = str(int(amount)) if amount == int(amount) else f"{amount:g}"
    if unit in PLURAL_UNITS and amount != 1:
        unit = PLURAL_UNITS[unit]
    return f"{shown} {unit}"


def line_quantity(line: ReceiptLine) -> tuple[float, str]:
    """Weight or pack size printed on the receipt, otherwise the number of units bought."""
    if line.weight:
        return round(line.weight, 2), "kg"
    if line.size:
        amount, unit = line.size
        return amount * line.count, unit
    return line.count, "piece"


def merge_into_detections(lines: list[ReceiptLine], answers: dict[int, dict]) -> list[dict]:
    """Combine model answers with the stated quantities: one row per ingredient and unit.

    Different ingredients stay separate rows; the same ingredient bought on
    several lines becomes one row with the quantities added together.
    """
    rows: dict[tuple[str, str], dict] = {}
    for line in lines:
        answer = answers.get(line.number)
        if not answer:
            continue
        amount, unit = line_quantity(line)
        key = (answer["ingredient"], unit)
        row = rows.setdefault(key, {"ingredient": answer["ingredient"], "amount": 0.0, "unit": unit, "receipt_lines": []})
        row["amount"] += amount
        row["receipt_lines"].extend(line.raw)

    detections = []
    for index, row in enumerate(rows.values(), start=1):
        descriptions: dict[str, int] = {}
        for raw in row["receipt_lines"]:
            text = _strip_price_and_junk(ITEM_CODE_PATTERN.sub("", raw))[0]
            descriptions[text] = descriptions.get(text, 0) + 1
        detections.append({
            "ingredient": row["ingredient"],
            "quantity": format_quantity(row["amount"], row["unit"]),
            "detection_id": f"receipt-{index}",
            "source": "Receipt",
            "visible_text": ", ".join(f"{text} ×{count}" if count > 1 else text for text, count in descriptions.items()),
        })
    return detections
