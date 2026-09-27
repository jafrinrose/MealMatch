"""Renders the receipt test images and their expected confirmation rows.

    venv/bin/python tests/fixtures/receipts/make_receipts.py

Each receipt mixes repeated lines, quantities stated on the receipt, common
abbreviations, look-alike foods that must stay separate, and non-food products.
The images are photographed-looking (slight tilt, blur and JPEG noise) so OCR
is exercised as well as the language model.
"""

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "/System/Library/Fonts/Menlo.ttc"

RECEIPTS = {
    "market-receipt": {
        "lines": [
            "      FRESHWAY MARKET",
            "      425 Harbour Rd",
            "    Tel (604) 555-0182",
            "2026/09/27 14:32    Lane 4",
            "",
            "GRK YGT PLAIN 750G      5.49",
            "GRK YGT PLAIN 750G      5.49",
            "CHKN BRST B/S          14.20",
            "EGGS LRG 12CT           4.79",
            "WHL MLK 4L              6.29",
            "SKM MLK 2L              3.99",
            "BANANAS",
            "  1.24 kg @ $1.52/kg    1.88",
            "AVOCADO",
            "  3 @ 1.29              3.87",
            "ROM LETTUCE             2.49",
            "RED ONION               1.10",
            "YELLOW ONION            0.95",
            "PNUT BTR 500G           4.49",
            "EVOO 1L                12.99",
            "KALAMATA OLV            6.99",
            "DAWN DISH SOAP          3.99",
            "PAPER TWL 6PK           8.99",
            "AA BATTERIES 8PK        9.99",
            "REUSABLE BAG            0.99",
            "SUBTOTAL              108.21",
            "TAX                     2.86",
            "TOTAL                 111.07",
            "VISA ************4417",
            "ITEMS SOLD 20",
            "  THANK YOU FOR SHOPPING",
        ],
        "expected": {
            "greek yogurt": "1500 g",
            "chicken breast": "1",
            "egg": "12 pieces",
            "whole milk": "4 l",
            "skim milk": "2 l",
            "banana": "1.24 kg",
            "avocado": "3",
            "romaine lettuce": "1",
            "red onion": "1",
            "yellow onion": "1",
            "peanut butter": "500 g",
            "extra virgin olive oil": "1 l",
            "kalamata olive": "1",
        },
        "excluded": ["dish soap", "paper towel", "batteries", "bag"],
    },
    "wholesale-receipt": {
        "lines": [
            "     BULKWAY WHOLESALE",
            "     #512 Riverside",
            "  Member 111822334455",
            "E   44120 B/S THIGHS     21.99",
            "E   27363 16/20 SHRIMP   30.57",
            "E   27363 16/20 SHRIMP   30.57",
            "E  776059 ARTISAN BGT     5.99",
            "E  776059 ARTISAN BGT     5.99",
            "E  776059 ARTISAN BGT     5.99",
            "  0000351 /776059         1.00-",
            "E  512515 ORG STRAWBRY    8.99",
            "E 1188673 PRSDNT BRIE     9.99",
            "E    1436 WHIP CREAM 1L   5.39",
            "E  216945 FETA CRMBL     14.89",
            "E   88426 ENG CUCUMBER 3CT 4.99",
            "E  174695 RUSSET POTATO 10LB 7.49",
            "E  960123 JASMINE RICE 8KG 21.99",
            "E  884422 KS PAPER TOWEL 24.99",
            "E  552211 TIDE PODS 81CT 29.99",
            "E  301177 KS BATH TISSUE 23.99",
            "E  145566 SPARKLING WTR 24PK 9.99",
            "   SUBTOTAL            271.73",
            "   TAX                   0.00",
            "**** TOTAL             271.73",
            "TOTAL NUMBER OF ITEMS SOLD = 17",
        ],
        "expected": {
            "chicken thigh": "1",
            "shrimp": "2",
            "baguette": "3",
            "strawberry": "1",
            "brie": "1",
            "whipping cream": "1 l",
            "feta": "1",
            "english cucumber": "3 pieces",
            "russet potato": "4.54 kg",
            "jasmine rice": "8 kg",
            "sparkling water": "24 pieces",
        },
        "excluded": ["paper towel", "tide", "bath tissue"],
    },
    # Written after the pipeline was tuned on the two receipts above and run once,
    # unchanged, as a check that the rules generalise (new abbreviations, "x3", £/kg).
    "holdout-receipt": {
        "lines": [
            "      GREENLEAF GROCERS",
            "    88 Market St, Leeds",
            "   VAT No 123 4567 89",
            "27/09/26 18:05      Till 2",
            "",
            "2 x SEMI SKIMMED MILK 2PT  2.30",
            "FREE RANGE EGGS 6PK        2.10",
            "GALA APPLES 6PK            1.95",
            "BRKFST SAUSAGE 454G        3.49",
            "BBY SPINACH 200G           1.50",
            "CHDR CHS MATURE 400G       3.25",
            "BASMATI RICE 1KG           2.40",
            "TIN TOMATOES 400G          0.55",
            "TIN TOMATOES 400G          0.55",
            "LOOSE CARROTS",
            "  0.512 kg @ £0.90/kg      0.46",
            "LEMONS x3                  0.90",
            "BIN BAGS 20PK              2.00",
            "KITCHEN ROLL 2PK           2.50",
            "TOOTHPASTE 75ML            1.80",
            "CAT FOOD POUCHES 12PK      4.50",
            "HUMMUS 200G                1.20",
            "OAT MILK 1L                1.60",
            "BALANCE DUE               38.46",
            "CARD PAYMENT              38.46",
        ],
        "expected": {
            "semi skimmed milk": "2",
            "egg": "6 pieces",
            "gala apple": "6 pieces",
            "breakfast sausage": "454 g",
            "baby spinach": "200 g",
            "cheddar": "400 g",
            "basmati rice": "1 kg",
            "tomato": "800 g",
            "carrot": "0.51 kg",
            "lemon": "3",
            "hummus": "200 g",
            "oat milk": "1 l",
        },
        "excluded": ["bin bag", "kitchen roll", "toothpaste", "cat food"],
    },
}


def render(lines: list[str], seed: int) -> Image.Image:
    rng = random.Random(seed)
    font = ImageFont.truetype(FONT, 26)
    line_height = 36
    paper = Image.new("L", (600, 60 + line_height * len(lines)), 250)
    draw = ImageDraw.Draw(paper)
    for index, text in enumerate(lines):
        draw.text((24, 30 + index * line_height), text, font=font, fill=rng.randint(25, 60))
    photo = Image.new("L", (paper.width + 160, paper.height + 160), 95)
    photo.paste(paper, (80, 80))
    photo = photo.rotate(rng.uniform(-1.2, 1.2), resample=Image.Resampling.BICUBIC, fillcolor=95)
    return photo.filter(ImageFilter.GaussianBlur(0.7)).convert("RGB")


if __name__ == "__main__":
    for seed, (name, receipt) in enumerate(RECEIPTS.items(), start=1):
        render(receipt["lines"], seed).save(HERE / f"{name}.jpg", quality=80)
        expected = {key: receipt[key] for key in ("expected", "excluded")}
        (HERE / f"{name}.expected.json").write_text(json.dumps(expected, indent=2) + "\n")
        print("wrote", name)
