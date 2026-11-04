# -*- coding: utf-8 -*-
"""
cook-forge - recipe technique and timing analysis engine.

Standard library only. No network calls, no API keys.

The engine answers one question: "If I make this recipe as written, what will
actually happen in my kitchen - and what do I change first?"
"""

import re
import json

# ---------------------------------------------------------------------------
# fractions and units
# ---------------------------------------------------------------------------

FRACTION_CHARS = {
    "\u00bc": 0.25, "\u00bd": 0.5, "\u00be": 0.75,
    "\u2153": 1.0 / 3, "\u2154": 2.0 / 3, "\u2158": 4.0 / 5,
    "\u215b": 0.125, "\u215c": 0.375, "\u215d": 0.625, "\u215e": 0.875,
    "\u2155": 0.2, "\u2156": 0.4, "\u2157": 0.6,
}

UNIT_ALIASES = {
    "c": "cup", "cup": "cup", "cups": "cup",
    "tbsp": "tbsp", "tbs": "tbsp", "tb": "tbsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "g": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml",
    "millilitre": "ml", "millilitres": "ml",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "clove": "clove", "cloves": "clove",
    "can": "can", "cans": "can", "tin": "can", "tins": "can",
    "package": "pkg", "pkg": "pkg", "packages": "pkg",
    "bunch": "bunch", "bunches": "bunch",
    "slice": "slice", "slices": "slice",
    "piece": "piece", "pieces": "piece",
    "head": "head", "heads": "head",
    "large": "size", "medium": "size", "small": "size",
    "quart": "quart", "quarts": "quart", "pint": "pint", "pints": "pint",
    "gallon": "gallon", "gallons": "gallon",
    "stick": "stick", "sticks": "stick",
    "handful": "handful", "handfuls": "handful",
    "dash": "dash", "dashes": "dash",
    "pinch": "pinch", "pinches": "pinch",
    "sprig": "sprig", "sprigs": "sprig",
    "stalk": "stalk", "stalks": "stalk",
    "jar": "jar", "jars": "jar",
    "scoop": "scoop", "scoops": "scoop",
    "cube": "cube", "cubes": "cube",
    "fillet": "fillet", "fillets": "fillet",
    "breast": "breast", "breasts": "breast",
    "thigh": "thigh", "thighs": "thigh",
    "bulb": "bulb", "bulbs": "bulb",
    "leaf": "leaf", "leaves": "leaf",
    "sheet": "sheet", "sheets": "sheet",
    "serving": "serving", "servings": "serving",
}

STOP_WORDS = set("""
fresh dried ground chopped diced sliced minced large medium small extra
virgin olive kosher sea fine coarse plain whole boneless skinless optional
best good quality ripe raw cooked low fat reduced sodium light organic
heaping scant generous finely thinly roughly about
""".split())

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


_FRAC_CLASS = "[" + "".join(re.escape(c) for c in FRACTION_CHARS) + "]"


def normalize_numbers(text):
    """Turn unicode fractions and mixed fractions into plain decimals."""
    if not text:
        return ""
    s = text
    s = re.sub(r"(\d+)\s+(\d+)\s*/\s*(\d+)",
               lambda m: str(int(m.group(1)) + int(m.group(2)) / float(m.group(3))), s)

    def frac_repl(m):
        whole = m.group(1)
        val = FRACTION_CHARS[m.group(2)]
        if whole:
            return str(int(whole) + val)
        return str(val)

    s = re.sub(r"(\d+)?\s*(" + _FRAC_CLASS + ")", frac_repl, s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_qty(text):
    """Return (quantity or None, remainder)."""
    t = (text or "").strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s+(\d+)\s*/\s*(\d+)", t)
    if m:
        return int(m.group(1)) + int(m.group(2)) / float(m.group(3)), t[m.end():].strip()
    m = re.match(r"^(\d+)\s*/\s*(\d+)", t)
    if m:
        return int(m.group(1)) / float(m.group(2)), t[m.end():].strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\b", t)
    if m:
        return float(m.group(1)), t[m.end():].strip()
    return None, t


def content_words(name):
    """Lowercase content words of an ingredient name, stop words removed."""
    base = re.sub(r"\(.*?\)", "", name or "")
    base = re.sub(r"[^a-zA-Z ]", " ", base.lower())
    words = [w for w in base.split() if len(w) > 2 and w not in STOP_WORDS]
    return words


def plural_to_singular(word):
    w = (word or "").lower().strip()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3 and not w.endswith(("ses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    if w.endswith("s") and len(w) > 3:
        return w[:-1]
    return w


def fmt_qty(q):
    if q is None:
        return ""
    if abs(q - round(q)) < 0.01:
        return str(int(round(q)))
    whole = int(q)
    frac = q - whole
    table = [(0.125, "1/8"), (0.25, "1/4"), (0.333, "1/3"), (0.375, "3/8"),
             (0.5, "1/2"), (0.625, "5/8"), (0.667, "2/3"), (0.75, "3/4"), (0.875, "7/8")]
    for val, label in table:
        if abs(frac - val) < 0.04:
            return ("%d %s" % (whole, label)).strip()
    return ("%.2f" % q).rstrip("0").rstrip(".")


def fmt_clock(minutes):
    if minutes is None:
        return "-"
    minutes = float(minutes)
    h = int(minutes // 60)
    m = int(round(minutes - h * 60))
    if m == 60:
        h += 1
        m = 0
    if h:
        return "%dh%02dm" % (h, m)
    return "%dm" % m


# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------

GAS_MARK_F = {1: 275, 2: 300, 3: 325, 4: 350, 5: 375, 6: 400, 7: 425, 8: 450, 9: 475}

OVEN_VERBS = {"bake", "bakes", "baked", "baking", "roast", "roasts", "roasted",
              "roasting", "broil", "broils", "broiled", "broiling", "preheat",
              "preheats", "preheated"}
STOVE_VERBS = {"sear", "sears", "seared", "searing", "saute", "sauted",
               "fry", "fries", "fried", "frying", "boil", "boils", "boiled",
               "boiling", "simmer", "simmers", "simmered", "simmering",
               "reduce", "reduces", "reduced", "reducing", "whisk", "whisks",
               "whisked", "whisking", "stir", "stirs", "stirred", "stirring",
               "deglaze", "deglazed", "toast", "toasts", "toasted", "toasting",
               "poach", "poached", "blanch", "blanched", "caramelize",
               "sweat", "sweated", "render", "melt", "melted", "griddle"}
FRIDGE_VERBS = {"chill", "chilled", "chilling", "refrigerate", "refrigerated",
                "marinate", "marinated", "marinating", "freeze", "frozen",
                "freezing", "cure", "cured", "soak", "soaked", "soaking",
                "brine", "brined", "brining", "rise", "rises", "risen",
                "proof", "proved", "rest", "rests", "rested", "resting",
                "cool", "cools", "cooled", "cooling"}
ACTIVE_VERBS = {"chop", "chopped", "chopping", "dice", "diced", "mince", "minced",
                "slice", "sliced", "slicing", "grate", "grated", "zest", "zested",
                "peel", "peeled", "trim", "trimmed", "fold", "folded", "knead",
                "kneaded", "mix", "mixed", "combine", "combined", "season",
                "seasoned", "garnish", "drizzle", "pour", "poured", "transfer",
                "sprinkle", "coat", "toss", "assemble", "roll", "rolled", "shape",
                "spread", "mash", "mashed", "blend", "blended", "beat", "beaten",
                "cut", "julienne", "cube", "brown", "add", "beat"}

PASSIVE_VERBS = set(OVEN_VERBS) | set(FRIDGE_VERBS) | {"simmer", "simmering",
                   "simmered", "reduce", "reducing", "reduced", "braise",
                   "braised", "braising", "poached", "soaked", "soaking",
                   "infuse", "steep", "steeped", "rest", "resting", "steam",
                   "steamed"}

# steps that genuinely need a clock: these are the ones a cook plans around
WAIT_RE = re.compile(
    r"\b(bake|bakes|baking|roast|roasts|roasting|broil|broiling|simmer|simmers|"
    r"simmering|boil|boils|boiling|braise|braising|reduce|reducing|poach|poached|"
    r"steam|steamed|chill|chilled|chilling|refrigerate|marinate|marinated|"
    r"marinating|freeze|frozen|soak|soaked|soaking|brine|brined|rise|rises|"
    r"proof|rest|rests|rested|until)\b", re.I)

PROTEINS = [
    ("ground beef", 160, "ground beef", False),
    ("ground turkey", 165, "ground turkey", False),
    ("ground pork", 160, "ground pork", False),
    ("chicken breast", 165, "chicken breast", True),
    ("chicken thigh", 165, "chicken thigh", True),
    ("chicken", 165, "chicken (poultry)", True),
    ("turkey", 165, "turkey (poultry)", True),
    ("duck", 165, "duck (poultry)", True),
    ("steak", 145, "steak", True),
    ("beef", 145, "beef (whole cuts)", True),
    ("pork chop", 145, "pork chop", True),
    ("pork", 145, "pork (whole cuts)", True),
    ("lamb", 145, "lamb (whole cuts)", True),
    ("salmon", 145, "salmon", False),
    ("fish", 145, "fish", False),
    ("shrimp", 145, "shrimp", False),
    ("scallop", 145, "scallop", False),
    ("sausage", 160, "sausage", False),
    ("bacon", 145, "bacon", False),
]

GROUND_MEATS = ("ground beef", "ground turkey", "ground pork")

FOOD_VOCAB = set("""
flour sugar butter egg eggs milk yogurt cheese parmesan mozzarella cheddar
feta ricotta mascarpone salt pepper garlic ginger scallion leek carrot celery
potato tomato lettuce spinach kale arugula cucumber zucchini eggplant bell
jalapeno mushroom broccoli cauliflower asparagus peas corn squash pumpkin
rice jasmine basmati arborio quinoa couscous barley oats bread breadcrumb
panko tortilla noodle pasta spaghetti penne linguine lasagna broth stock
vinegar beer mayonnaise ketchup lime lemon orange apple banana avocado mango
pineapple blueberry strawberry raspberry peanut sesame artichoke capers
anchovy nori seaweed chickpea lentil bean tofu tempeh honey vanilla cinnamon
nutmeg paprika cumin coriander turmeric Worcestershire mustard Dijon
chicken steak salmon shrimp bacon sausage turkey lamb pork scallop
""".split())

PROTEIN_FAMILY = {
    "beef": ["beef", "steak", "brisket", "roast", "burger"],
    "chicken": ["chicken", "breast", "thigh", "drumstick", "wing"],
    "pork": ["pork", "chop", "bacon", "ham", "ribs"],
    "lamb": ["lamb"],
    "turkey": ["turkey"],
    "fish": ["fish", "salmon", "tuna", "cod", "scallop"],
    "shrimp": ["shrimp", "prawn"],
}

# ---------------------------------------------------------------------------
# recipe parsing
# ---------------------------------------------------------------------------

HEADER_KEYS = {
    "title": ["title", "name", "recipe"],
    "servings": ["serves", "servings", "yield", "makes", "portions"],
    "time": ["time", "total time", "total", "cook time", "elapsed"],
    "prep": ["prep time", "prep"],
    "equipment": ["equipment", "tools", "gear", "you will need", "you'll need"],
    "skill": ["skill", "skill level", "level", "difficulty"],
    "notes": ["notes", "note"],
}

SECTION_STEPS = re.compile(r"^\s*(?:#{1,4}\s*)?(steps|directions|direction|instructions|instruction|method|procedure|preparation)\s*:?\s*$", re.I)
SECTION_ING = re.compile(r"^\s*(?:#{1,4}\s*)?(ingredients?|shopping list)\s*:?\s*$", re.I)
SECTION_NOTES = re.compile(r"^\s*(?:#{1,4}\s*)?notes?\s*:?\s*$", re.I)

DUR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:(?:-|\u2013|\u2014|to|or)\s*(\d+(?:\.\d+)?)\s*)?(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", re.I)
OVEN_F_RE = re.compile(r"(\d{2,3})\s*(?:\u00b0|degrees?|deg)?\s*F(?![A-Za-z])", re.I)
OVEN_C_RE = re.compile(r"(\d{2,3})\s*(?:\u00b0|degrees?|deg)?\s*C(?![A-Za-z])")
GAS_RE = re.compile(r"gas\s*mark\s*(\d)", re.I)
OVEN_TEMP_CONTEXT = re.compile(r"\b(oven|bake|roast|preheat|baking sheet|casserole)\b", re.I)
HEAT_RE = re.compile(r"\b(low|medium|medium-low|medium-high|high|gentle|moderate)\b(?:\s*heat)?", re.I)

TIME_TO_MIN = {"second": 1 / 60, "seconds": 1 / 60, "sec": 1 / 60, "secs": 1 / 60,
               "minute": 1, "minutes": 1, "min": 1, "mins": 1,
               "hour": 60, "hours": 60, "hr": 60, "hrs": 60}

INDEFINITE_RE = re.compile(r"\b(overnight|until tender|until done|until cooked|as needed|to taste|until set|until golden|until brown|until thickened|until reduced|until fluffy)\b", re.I)


def parse_duration(text):
    """Return (minutes_min, minutes_max, label) for the first duration in text."""
    t = normalize_numbers(text or "")
    for m in DUR_RE.finditer(t):
        unit = m.group(3).lower()
        unit = re.sub(r"s$", "", unit)
        unit = {"sec": "sec", "secs": "sec", "min": "minute", "mins": "minute",
                "hr": "hour", "hrs": "hour"}.get(unit, unit)
        factor = TIME_TO_MIN.get(unit, 1)
        lo = float(m.group(1)) * factor
        hi = float(m.group(2)) * factor if m.group(2) else lo
        label = m.group(0).strip()
        return lo, max(hi, lo), label
    return None, None, None


def total_duration(text):
    """Sum every duration in a header such as '1 hour 15 minutes'."""
    t = normalize_numbers(text or "")
    total = 0.0
    found = False
    for m in DUR_RE.finditer(t):
        unit = m.group(3).lower()
        unit = re.sub(r"s$", "", unit)
        unit = {"sec": "sec", "secs": "sec", "min": "minute", "mins": "minute",
                "hr": "hour", "hrs": "hour"}.get(unit, unit)
        factor = TIME_TO_MIN.get(unit, 1)
        lo = float(m.group(1)) * factor
        hi = float(m.group(2)) * factor if m.group(2) else lo
        total += max(hi, lo)
        found = True
    return total if found else None


def parse_oven_temp(text):
    t = normalize_numbers(text or "")
    f = OVEN_F_RE.search(t)
    c = OVEN_C_RE.search(t)
    gas = GAS_RE.search(t)
    if f and (c is None or f.start() <= c.start()):
        val = int(f.group(1))
        if 150 <= val <= 550:
            return val, None, f.group(0).strip()
    if c:
        val = int(c.group(1))
        if 70 <= val <= 300:
            return None, val, c.group(0).strip()
    if gas:
        f_val = GAS_MARK_F.get(int(gas.group(1)))
        if f_val:
            return f_val, None, gas.group(0).strip()
    return None, None, None


def parse_ingredients(lines):
    out = []
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        raw = re.sub(r"^[\-\*\u2022]\s*", "", raw)
        raw = re.sub(r"^\(?\d+[\.\)]\s+", "", raw)
        if not raw:
            continue
        norm = normalize_numbers(raw)
        qty, rest = parse_qty(norm)
        unit = None
        if rest:
            m = re.match(r"^([a-zA-Z]+)\b", rest)
            if m and m.group(1).lower() in UNIT_ALIASES:
                unit = UNIT_ALIASES[m.group(1).lower()]
                rest = rest[m.end():].strip()
        name = rest
        prep = ""
        if "(" in name:
            head, _, tail = name.partition("(")
            name = head.strip()
            prep = tail.rstrip(")").strip()
        elif "," in name:
            head, _, tail = name.partition(",")
            name = head.strip()
            prep = tail.strip()
        name = re.sub(r"^(of|about|approx\.?|roughly)\s+", "", name, flags=re.I).strip()
        out.append({
            "raw": raw, "qty": qty, "unit": unit,
            "name": name or raw, "prep": prep,
            "key": ingredient_key(name or raw),
        })
    return out


def ingredient_key(name):
    words = content_words(name)
    if words:
        return words[-1]
    base = re.sub(r"[^a-zA-Z ]", " ", (name or "").lower())
    parts = base.split()
    return parts[-1] if parts else (name or "").strip()


def parse_steps(lines):
    out = []
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        raw = re.sub(r"^\(?\d+[\.\)]\s+", "", raw)
        raw = re.sub(r"^[\-\*\u2022]\s*", "", raw)
        raw = re.sub(r"^(step\s*\d+[:\.\)]?)\s*", "", raw, flags=re.I)
        if not raw:
            continue
        norm = normalize_numbers(raw)
        lo, hi, dur_label = parse_duration(norm)
        temp_f, temp_c, temp_label = (None, None, None)
        if OVEN_TEMP_CONTEXT.search(norm):
            temp_f, temp_c, temp_label = parse_oven_temp(norm)
        words = set(re.findall(r"[a-z]+", norm.lower()))
        has_oven = bool(words & OVEN_VERBS) or bool(re.search(r"\bin the oven\b", norm, re.I))
        has_stove = bool(words & STOVE_VERBS)
        has_fridge = bool(words & FRIDGE_VERBS)
        if has_oven:
            station = "oven"
        elif has_fridge and not has_stove:
            station = "fridge"
        elif has_stove:
            station = "stovetop"
        else:
            station = "prep"
        active_hit = bool(words & ACTIVE_VERBS)
        passive_hit = bool(words & PASSIVE_VERBS)
        indefinite = bool(INDEFINITE_RE.search(norm))
        if passive_hit and not active_hit:
            passive = True
        elif has_oven and not active_hit:
            passive = True
        elif lo is not None and lo >= 20 and not active_hit:
            passive = True
        else:
            passive = False
        verbs = sorted(words & (OVEN_VERBS | STOVE_VERBS | FRIDGE_VERBS | ACTIVE_VERBS))
        out.append({
            "index": len(out) + 1,
            "text": raw,
            "duration": hi if hi is not None else lo,
            "duration_min": lo,
            "duration_max": hi,
            "duration_label": dur_label,
            "oven_temp_f": temp_f,
            "oven_temp_c": temp_c,
            "oven_temp_label": temp_label,
            "station": station,
            "passive": passive,
            "indefinite": indefinite,
            "expects_time": bool(WAIT_RE.search(norm)),
            "verbs": verbs,
            "heat": (HEAT_RE.search(norm).group(0).lower() if HEAT_RE.search(norm) else None),
        })
    return out


def parse_recipe(raw_text):
    raw_text = raw_text or ""
    lines = raw_text.splitlines()
    meta = {}
    ing_lines, step_lines = [], []
    mode = "head"
    ing_started = False
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if SECTION_ING.match(s):
            mode = "ing"
            ing_started = True
            continue
        if SECTION_STEPS.match(s):
            mode = "steps"
            continue
        if SECTION_NOTES.match(s):
            mode = "notes"
            continue
        if mode == "head":
            m = re.match(r"^([A-Za-z][A-Za-z \-]{1,22}?)\s*:\s*(.+)$", s)
            if m:
                key = m.group(1).strip().lower()
                value = m.group(2).strip()
                matched = False
                for hkey, aliases in HEADER_KEYS.items():
                    if key in aliases:
                        meta[hkey] = value
                        matched = True
                        break
                if not matched:
                    ing_lines.append(s)
                continue
            if ing_started:
                ing_lines.append(s)
            else:
                step_lines.append(s)
            continue
        if mode == "ing":
            ing_lines.append(s)
        elif mode == "steps":
            step_lines.append(s)
        else:
            meta["notes"] = (meta.get("notes", "") + " " + s).strip()

    if not ing_lines and not step_lines:
        bullets = [l for l in lines if re.match(r"^\s*[\-\*\u2022]", l)]
        numbered = [l for l in lines if re.match(r"^\s*\d+[\.\)]", l)]
        if bullets and numbered:
            ing_lines = bullets
            step_lines = numbered
        elif bullets:
            ing_lines = bullets
        elif numbered:
            step_lines = numbered
        else:
            step_lines = [l for l in lines if l.strip()]

    ingredients = parse_ingredients(ing_lines)
    steps = parse_steps(step_lines)

    servings = None
    yield_text = ""
    raw_servings = meta.get("servings")
    if raw_servings:
        value = raw_servings.strip()
        if re.search(r"\b(cookies?|biscuits?|cupcakes?|muffins?|brownies?|bars?|scones?)\b", value, re.I):
            yield_text = value
        else:
            m = re.search(r"(\d+(?:\.\d+)?)", normalize_numbers(value))
            if m:
                servings = float(m.group(1))
    if servings is None and not yield_text:
        m = re.search(r"\bserves\s+(\d+)", raw_text, re.I)
        if m:
            servings = float(m.group(1))

    claimed = total_duration(meta.get("time"))
    prep_min = total_duration(meta.get("prep"))

    return {
        "title": meta.get("title") or "Untitled recipe",
        "servings": servings,
        "yield_text": yield_text,
        "claimed_minutes": claimed,
        "prep_minutes": prep_min,
        "equipment_declared": meta.get("equipment", ""),
        "skill": meta.get("skill", ""),
        "notes": meta.get("notes", ""),
        "ingredients": ingredients,
        "steps": steps,
        "raw": raw_text,
    }


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------


def build_timeline(steps):
    """Schedule the steps the way a cook actually runs them.

    The cook works in order: step N starts no earlier than step N-1 finished.
    An unattended step (bake, simmer, chill) releases the cook but still
    occupies its station, so the next hands-on step overlaps with it.
    """
    cook_free = 0.0
    prev_end = 0.0
    res_free = {"oven": 0.0, "stovetop": 0.0, "fridge": 0.0, "prep": 0.0, "grill": 0.0}
    rows = []
    for s in steps:
        dur = s.get("duration") or 0.0
        estimated = False
        if not dur and not s["passive"]:
            dur = 2.0
            estimated = True
        res = s["station"]
        start = max(prev_end, cook_free, res_free.get(res, 0.0))
        end = start + dur
        res_free[res] = max(res_free.get(res, 0.0), end)
        if not s["passive"]:
            cook_free = end
        prev_end = end
        rows.append({
            "index": s["index"],
            "text": s["text"],
            "station": res,
            "start": round(start, 1),
            "end": round(end, 1),
            "duration": round(dur, 1),
            "estimated": estimated,
            "passive": s["passive"],
            "indefinite": s["indefinite"],
            "oven_temp_f": s.get("oven_temp_f"),
            "oven_temp_c": s.get("oven_temp_c"),
        })
    total = max([cook_free, prev_end] + list(res_free.values())) if rows else 0.0
    hands_on = 0.0
    untimed_active = 0
    for r, s in zip(rows, steps):
        if s["passive"]:
            continue
        hands_on += r["duration"]
        if r.get("estimated"):
            untimed_active += 1
    return rows, round(total, 1), round(hands_on, 1), untimed_active


# ---------------------------------------------------------------------------
# equipment
# ---------------------------------------------------------------------------

EQUIPMENT = [
    ("oven", ["bake", "baking", "roast", "roasting", "broil", "preheat", "oven", "casserole"],
     "Any countertop oven works; for small batches a Dutch oven on the stovetop can substitute."),
    ("blender", ["blend", "blender", "puree", "purée"],
     "A stick blender in a tall pot works, or pulse in a food processor."),
    ("food processor", ["food processor", "pulse"],
     "A blender plus a little patience, or hand-chop for a smaller batch."),
    ("stand mixer", ["stand mixer", "paddle attachment", "dough hook", "mixer"],
     "A hand mixer with a bowl works; for bread dough, mix by hand and knead on a floured surface."),
    ("hand mixer", ["hand mixer", "electric mixer"],
     "Whisk by hand for small batches, in two bowls for bigger ones."),
    ("immersion blender", ["immersion blender", "stick blender"],
     "Blend in a tall pot with a stick blender, or transfer to a countertop blender."),
    ("dutch oven", ["dutch oven", "heavy pot", "braiser", "stockpot", "large pot"],
     "Any heavy lidded pot with an oven-safe lid does the same job."),
    ("cast iron skillet", ["cast iron", "skillet", "cast-iron", "frying pan"],
     "A heavy stainless or carbon steel skillet works; a nonstick pan sears less aggressively but will do."),
    ("sheet pan", ["sheet pan", "baking sheet", "rimmed baking sheet", "cookie sheet"],
     "Use a rimmed tray or the bottom of an oven-safe pan; avoid crowding."),
    ("cake pan", ["9x13", "9 x 13", "cake pan", "rectangular pan", "bundt", "loaf pan",
                  "springform", "ramekin", "muffin tin", "cupcake"],
     "Any similar-volume oven-safe dish works; adjust the bake time if the depth changes."),
    ("wok", ["wok"],
     "A large cast iron skillet or carbon steel pan works for stir-frying."),
    ("grill", ["grill", "charcoal", "gas grill", "barbecue"],
     "A hot cast iron skillet under the broiler works as a grill substitute."),
    ("slow cooker", ["slow cooker", "crock pot"],
     "A Dutch oven in a 160F oven gets you the same long, gentle cook."),
    ("instant pot", ["instant pot", "pressure cooker"],
     "A stovetop pressure cooker or a covered pot with a shorter cook time works."),
    ("air fryer", ["air fryer"],
     "A conventional oven on a similar temperature gets close enough."),
    ("microwave", ["microwave"],
     "Use a stovetop double boiler for even heating, in short bursts."),
    ("mandoline", ["mandoline", "julienne"],
     "A sharp knife and a steady hand work; keep your knuckles out of the way."),
    ("immersion circulator", ["sous vide", "immersion circulator"],
     "Bake the food in a sealed bag at the same temperature instead."),
    ("food scale", ["food scale", "kitchen scale"],
     "A volume measure is close enough for most recipes; weigh for bread and seasoning."),
    ("probe thermometer", ["thermometer", "instant-read", "instant read", "probe"],
     "A supermarket probe thermometer costs little and removes the guesswork."),
    ("cleaver", ["cleaver"],
     "A chef's knife works for most tasks."),
    ("tortilla press", ["tortilla press"],
     "Press between two flat pans weighted with a can, or a heavy skillet."),
    ("pizza stone", ["pizza stone", "pizza steel"],
     "A preheated upside-down sheet pan gives a similar crisp base."),
]

GEAR_ALIASES = {
    "oven": ["oven", "range oven", "built in oven", "stove oven"],
    "blender": ["blender", "vitamix", "nutribullet"],
    "food processor": ["food processor"],
    "stand mixer": ["stand mixer", "kitchenaid", "kitchen aid", "mixer"],
    "hand mixer": ["hand mixer", "handheld mixer"],
    "immersion blender": ["immersion blender", "stick blender"],
    "dutch oven": ["dutch oven", "le creuset", "braiser", "stockpot", "large pot", "saucepan"],
    "cast iron skillet": ["cast iron", "skillet", "frying pan", "saute pan"],
    "sheet pan": ["sheet pan", "baking sheet", "rimmed sheet", "cookie sheet", "tray"],
    "cake pan": ["cake pan", "loaf pan", "9x13", "bundt", "springform", "muffin tin", "ramekin"],
    "wok": ["wok"],
    "grill": ["grill", "barbecue", "bbq"],
    "slow cooker": ["slow cooker", "crockpot", "crock pot"],
    "instant pot": ["instant pot", "pressure cooker"],
    "air fryer": ["air fryer"],
    "microwave": ["microwave"],
    "mandoline": ["mandoline"],
    "immersion circulator": ["sous vide", "immersion circulator"],
    "food scale": ["food scale", "kitchen scale", "scale"],
    "probe thermometer": ["thermometer", "instant read", "instant-read"],
    "cleaver": ["cleaver", "knife", "chef knife"],
    "tortilla press": ["tortilla press"],
    "pizza stone": ["pizza stone", "pizza steel"],
}

CRITICAL_TOOLS = {"oven", "probe thermometer", "stand mixer", "blender"}

# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

SEVERITY_POINTS = {"critical": 30, "high": 18, "medium": 9, "low": 4}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

INTENT_WEIGHTS = {
    "balanced": {"timing": 0.24, "technique": 0.24, "sequencing": 0.20, "completeness": 0.18, "equipment": 0.14},
    "weeknight": {"timing": 0.32, "technique": 0.18, "sequencing": 0.20, "completeness": 0.14, "equipment": 0.16},
    "showstopper": {"timing": 0.12, "technique": 0.32, "sequencing": 0.18, "completeness": 0.24, "equipment": 0.14},
    "beginner": {"timing": 0.20, "technique": 0.28, "sequencing": 0.14, "completeness": 0.24, "equipment": 0.14},
    "batch": {"timing": 0.18, "technique": 0.22, "sequencing": 0.30, "completeness": 0.20, "equipment": 0.10},
    "entertaining": {"timing": 0.26, "technique": 0.22, "sequencing": 0.22, "completeness": 0.16, "equipment": 0.14},
}

AXES = ["timing", "technique", "sequencing", "completeness", "equipment"]

VERDICTS = [
    (85, "ready_to_cook", "Ready to cook"),
    (70, "mostly_ready", "Mostly ready"),
    (55, "needs_tweaks", "Needs tweaks"),
    (40, "tight_but_usable", "Tight but usable"),
    (0, "needs_rework", "Needs rework"),
]

OVEN_BANDS = {
    "cookie": (325, 375), "brownie": (325, 350), "scone": (400, 450),
    "bread": (400, 450), "pizza": (475, 500), "roast": (325, 450),
    "fish": (375, 425), "salmon": (375, 425), "vegetable": (400, 450),
    "potato": (400, 450), "lasagna": (375, 400), "custard": (300, 325),
    "muffin": (350, 400), "pie": (375, 400), "chicken": (400, 450),
    "casserole": (325, 375), "meringue": (300, 340), "quiche": (325, 350),
    "cookie": (325, 375),
}


# ---------------------------------------------------------------------------
# findings engine
# ---------------------------------------------------------------------------


class Findings(object):
    def __init__(self):
        self.items = []

    def add(self, fid, severity, axis, title, evidence, why, fix, gain=None):
        self.items.append({
            "id": fid,
            "severity": severity,
            "axis": axis,
            "title": title,
            "evidence": (evidence or "").strip()[:220],
            "why": why,
            "fix": fix,
            "gain": gain if gain is not None else round(
                SEVERITY_POINTS.get(severity, 4) * (INTENT_WEIGHTS["balanced"].get(axis, 0.2)), 1),
        })

    def has(self, fid):
        return any(i["id"] == fid for i in self.items)

    def count(self, severity):
        return sum(1 for i in self.items if i["severity"] == severity)

    def total_points(self):
        return sum(SEVERITY_POINTS.get(i["severity"], 4) for i in self.items)


# ---------------------------------------------------------------------------
# main analysis
# ---------------------------------------------------------------------------


def analyze(recipe_text, context=None):
    ctx = {
        "gear": "",
        "target_servings": None,
        "intent": "balanced",
        "time_available": None,
        "skill": "",
    }
    if context:
        for k in list(ctx.keys()):
            if k in context and context[k] not in (None, ""):
                ctx[k] = context[k]
    try:
        ctx["target_servings"] = float(ctx["target_servings"]) if ctx["target_servings"] else None
    except (TypeError, ValueError):
        ctx["target_servings"] = None
    try:
        ctx["time_available"] = float(ctx["time_available"]) if ctx["time_available"] else None
    except (TypeError, ValueError):
        ctx["time_available"] = None
    if ctx["intent"] not in INTENT_WEIGHTS:
        ctx["intent"] = "balanced"

    recipe = parse_recipe(recipe_text)
    steps = recipe["steps"]
    ings = recipe["ingredients"]
    full_text = "\n".join([s["text"] for s in steps])
    norm_text = normalize_numbers(full_text).lower()
    ing_text = " ".join(i["raw"] for i in ings).lower()
    text_low = full_text.lower()

    F = Findings()
    strengths = []

    if not steps:
        F.add("no_steps", "critical", "completeness", "No steps found",
              (recipe_text or "")[:120],
              "The recipe has no parseable steps, so there is nothing to time, sequence or check.",
              "Add a numbered list of steps (one action per line) under a 'Steps:' heading.")
        return _finalize(recipe, ctx, F, strengths, [], 0, 0, 0, [])

    # ---------------- ingredient / step cross-check ----------------
    for i in ings:
        words = content_words(i["name"])
        if not words:
            continue
        hit = False
        for w in words:
            if w in norm_text or plural_to_singular(w) in norm_text:
                hit = True
                break
        if not hit:
            F.add("ingredient_unused", "medium", "completeness",
                  "Listed but never used: %s" % i["name"],
                  i["raw"],
                  "An ingredient nobody uses is either a leftover line or a step you forgot to write.",
                  "Use it in a step, or delete it from the list.")

    used_foods = set(w for w in re.findall(r"[a-z]+", norm_text) if w in FOOD_VOCAB)
    listed_words = set()
    for i in ings:
        for w in re.findall(r"[a-z]+", i["raw"].lower()):
            listed_words.add(w)
            listed_words.add(plural_to_singular(w))
    missing_foods = []
    for w in sorted(used_foods):
        if w in listed_words:
            continue
        family = PROTEIN_FAMILY.get(w)
        if family and any(re.search(r"\b%s\b" % re.escape(m), ing_text) for m in family):
            continue
        missing_foods.append(w)
    for w in missing_foods[:6]:
        F.add("ingredient_unlisted", "high", "completeness",
              "Used in the steps but not on the ingredient list: %s" % w,
              w,
              "You cannot shop for what is not listed, and the ratios will be wrong.",
              "Add '%s' to the ingredient list with a quantity." % w)
    if not missing_foods:
        strengths.append("Every ingredient that appears in the steps is on the list.")

    # ---------------- timing ----------------
    timeline, total_min, hands_on, untimed_active = build_timeline(steps)
    serial_sum = sum((s["duration"] or 0) for s in steps)
    timed_steps = sum(1 for s in steps if s["duration"])
    wait_steps = [s for s in steps if s["expects_time"]]
    timed_wait = sum(1 for s in wait_steps if s["duration"])
    indefinite_steps = sum(1 for s in steps if s["indefinite"] and not s["duration"])
    time_coverage = (timed_wait / float(len(wait_steps))) if wait_steps else 1.0

    claimed = recipe["claimed_minutes"]
    if claimed and total_min:
        if total_min > claimed * 1.25 and total_min - claimed >= 8:
            F.add("time_mismatch", "high", "timing",
                  "The clock says %s but the steps take about %s" % (fmt_clock(claimed), fmt_clock(total_min)),
                  "Recipe time: %s" % fmt_clock(claimed),
                  "Cooks trust the headline time and burn dinner when the steps quietly need longer.",
                  "Set the real time to %s (about %s hands-on) and start %s early."
                  % (fmt_clock(total_min), fmt_clock(hands_on), fmt_clock(total_min - claimed)))
        elif claimed > total_min * 1.5 and claimed - total_min >= 12:
            F.add("time_mismatch", "medium", "timing",
                  "Headline time %s is much longer than the steps need (%s)" % (fmt_clock(claimed), fmt_clock(total_min)),
                  "Recipe time: %s" % fmt_clock(claimed),
                  "An inflated headline time is how a 25 minute dinner becomes a 45 minute one.",
                  "Trim the headline to %s or add the steps that eat the difference." % fmt_clock(total_min))
    if time_coverage < 0.5 and wait_steps:
        F.add("no_timing", "medium", "timing",
              "Only %d of %d cooking steps carry a time" % (timed_wait, len(wait_steps)),
              "", "Without times on the cooking steps you are cooking blind and guessing at every stage.",
              "Add a duration to the long steps (bake, simmer, chill, rest) so the timeline is real.")
    elif wait_steps:
        strengths.append("Every cooking step (%d of %d) has a time attached." % (timed_wait, len(wait_steps)))
    if indefinite_steps:
        F.add("indefinite_step", "low", "timing",
              "%d step(s) have no clock time (until golden, until tender)" % indefinite_steps,
              "", "Until-done steps are where recipes go wrong - you cannot plan around them.",
              "Give a test: colour, texture, or internal temperature that defines done.")
    savings = serial_sum - total_min
    if savings >= 15:
        F.add("parallel_miss", "medium", "timing",
              "You can overlap the passive steps and save about %s" % fmt_clock(savings),
              "", "The steps are written as a straight line, so the oven and the stove are idle at the same time.",
              "Start the long bake or chill first and do the prep while it runs.")

    # oven preheat logic
    oven_steps = [s for s in steps if s["station"] == "oven"]
    preheat_idx = None
    first_oven_use = None
    for s in steps:
        low = s["text"].lower()
        if "preheat" in low or "heat the oven" in low:
            preheat_idx = s["index"] if preheat_idx is None else min(preheat_idx, s["index"])
        if s["station"] == "oven" and "preheat" not in low and first_oven_use is None:
            first_oven_use = s["index"]
    if oven_steps:
        if preheat_idx is None:
            F.add("no_preheat", "medium", "technique",
                  "The oven is used but never preheated",
                  oven_steps[0]["text"][:120],
                  "Food goes into a cold oven and comes out pale and uneven - and the stated bake time is a guess.",
                  "Add 'Preheat the oven to %s' as step 1 and allow 10-15 minutes for it."
                  % ((oven_steps[0].get("oven_temp_f") and ("%dF" % oven_steps[0]["oven_temp_f"])) or "the stated temperature"))
        elif first_oven_use and preheat_idx > first_oven_use:
            F.add("preheat_late", "high", "sequencing",
                  "The preheat comes after the first thing goes in the oven",
                  "Preheat is step %d, first oven use is step %d" % (preheat_idx, first_oven_use),
                  "The oven never reaches temperature, so the bake starts cold and the timing is fiction.",
                  "Move the preheat to the very first step.")
        else:
            strengths.append("The oven is preheated before it is used.")
        temps = sorted(set(s["oven_temp_f"] for s in oven_steps if s.get("oven_temp_f")))
        if len(temps) > 1:
            F.add("oven_temp_change", "low", "sequencing",
                  "The oven changes temperature mid-recipe (%s)" % ", ".join("%dF" % t for t in temps),
                  "", "Each change costs 10-15 minutes of preheat time that is not in the recipe.",
                  "Group the same-temperature steps together, or add 15 minutes between temperature changes.")
        for s in oven_steps:
            if s.get("oven_temp_c") and not s.get("oven_temp_f"):
                F.add("oven_temp_celsius", "low", "technique",
                      "Oven temperature is in Celsius (%dC) only" % s["oven_temp_c"],
                      s["text"][:100],
                      "Mixing C and F is how a recipe gets baked 80 degrees too hot.",
                      "Write it as %dF / %dC so nobody has to convert."
                      % (int(s["oven_temp_c"] * 9 / 5 + 32), s["oven_temp_c"]))

    # a long unattended step should come first, not last
    long_passive = [s for s in steps if s["passive"] and (s["duration"] or 0) >= 30
                    and s["station"] == "fridge"]
    if long_passive:
        first_long = min(s["index"] for s in long_passive)
        longest = max((s["duration"] or 0) for s in long_passive)
        if any(s["index"] < first_long and not s["passive"] for s in steps):
            F.add("passive_late", "medium", "sequencing",
                  "A %s chill or rest step only starts at the end of the recipe" % fmt_clock(longest),
                  "", "A long chill belongs at the front of the cook, not after everything else is done.",
                  "Move the chill, marinade or rest to step 1 and let it run while you cook.")

    # chill / rest / marinade expectations
    if re.search(r"\b(no[- ]bake|cheesecake|ice cream|panna cotta|tiramisu)\b", text_low) and not re.search(r"\b(chill|refrigerat|freeze|set)\b", text_low):
        F.add("chill_missing", "high", "completeness",
              "A no-bake dessert with no chilling step",
              "", "No-bake desserts need hours of set time in the fridge; skipping it leaves a puddle.",
              "Add 'Chill at least 4 hours (ideally overnight) until set' and add that to the total time.")
    if re.search(r"\b(marinade|marinate)\b", text_low):
        m = re.search(r"marinat\w*\b[^.\d]{0,40}?(\d+(?:\.\d+)?)\s*(minutes?|hours?|mins?)", norm_text)
        if m and float(m.group(1)) < 30:
            F.add("marinade_short", "medium", "technique",
                  "Marinating time is only %s" % m.group(0),
                  m.group(0),
                  "Under 30 minutes of marinade mostly just seasons the surface; it does not flavour the meat.",
                  "Give it at least 30 minutes for thin cuts and 2-8 hours for larger pieces.")
    if re.search(r"\b(brine|soak)\b", text_low):
        m = re.search(r"(?:brine|soak)\w*\b[^.\d]{0,40}?(\d+(?:\.\d+)?)\s*(minutes?|hours?)", norm_text)
        if m and float(m.group(1)) < 20:
            F.add("brine_short", "medium", "technique",
                  "The brine or soak is only %s" % m.group(0),
                  m.group(0),
                  "A short soak does not season or tenderise anything.",
                  "Use at least 30 minutes, and 2-4 hours if the goal is tenderising.")
    rest_match = re.search(r"rest\w*\b[^.\d]{0,40}?(\d+(?:\.\d+)?)\s*minutes?", norm_text)
    if rest_match:
        rest_min = float(rest_match.group(1))
        if rest_min < 5:
            F.add("rest_short", "medium", "technique",
                  "Rest time is only %d minutes" % int(rest_min),
                  rest_match.group(0),
                  "Resting lets the juices redistribute; under 5 minutes and the meat dries out on the board.",
                  "Rest 8-10 minutes for steaks, 15-20 minutes for a roast, 30 minutes for a whole bird.")
        elif rest_min < 15 and re.search(
                r"\b(chicken|turkey|duck|brisket|shoulder|leg of|pork|whole bird)\b", text_low):
            F.add("rest_short", "medium", "technique",
                  "Rest time is only %d minutes for a large cut" % int(rest_min),
                  rest_match.group(0),
                  "A big cut needs a real rest. Pulling it early means the juice ends up on the board.",
                  "Rest 20-30 minutes for a whole bird or a large roast before carving.")

    # ---------------- protein / food safety ----------------
    protein_hits = []
    protein_text = text_low + " " + ing_text
    for key, min_f, label, needs_rest in PROTEINS:
        if re.search(r"\b%s\b" % re.escape(key), protein_text):
            protein_hits.append((key, min_f, label, needs_rest))
    thin_cut = bool(re.search(r"\b(stir[- ]fry|stir[- ]fried|thinly sliced|thin strips|thin slices|sliced thin|julienned)\b", text_low))
    simmer_minutes = [int(x) for x in re.findall(
        r"(?:simmer|braise)\w*\b[^.\d]{0,30}?(\d+)\s*(?:minutes|mins)", norm_text)]
    long_simmer = bool(simmer_minutes) and max(simmer_minutes) >= 45
    if protein_hits:
        key, min_f, label, needs_rest = protein_hits[0]
        is_ground = key in GROUND_MEATS
        temps_f = [int(x) for x in re.findall(r"(\d{3})\s*(?:\u00b0|degrees?)?\s*F(?![A-Za-z])", full_text)]
        temps_c = [int(x) for x in re.findall(r"(\d{2,3})\s*(?:\u00b0|degrees?)?\s*C(?![A-Za-z])", full_text)]
        stated = [t for t in temps_f if 100 <= t <= 250]
        unsafe = False
        for t in stated:
            if t < min_f - 2:
                unsafe = True
                F.add("temp_unsafe", "critical", "technique",
                      "%s pulled at %dF is under the safe minimum of %dF" % (label, t, min_f),
                      "%dF" % t,
                      "This is the one finding that makes people sick. Poultry and ground meat must hit the safe temperature.",
                      "Cook to %dF (%dC) in the thickest part and rest before carving."
                      % (min_f, int((min_f - 32) * 5 / 9)))
                break
        if "medium rare" in text_low and key in ("chicken", "chicken breast", "turkey", "duck"):
            F.add("temp_unsafe", "critical", "technique",
                  "Medium rare on poultry is a food safety problem",
                  "medium rare",
                  "Poultry is not safe until it reaches 165F. This is a dangerous instruction to copy.",
                  "Cook poultry to 165F and rest it - the texture will still be good.")
        if not stated and not temps_c and re.search(r"\b(roast|bake|grill|sear|cook|pan[- ]fry)\b", text_low):
            if is_ground and long_simmer:
                strengths.append("A long simmer makes the ground beef safe without a thermometer.")
            else:
                sev = "medium" if is_ground else ("low" if thin_cut else "high")
                F.add("internal_temp_missing", sev, "technique",
                      "No internal temperature for %s" % label,
                      "", "Until golden is not a temperature. You cannot confirm the food is safe or cooked the way you meant.",
                      ("Pull it at %dF (%dC) in the thickest part and check with a probe."
                       % (min_f, int((min_f - 32) * 5 / 9))) if not thin_cut else
                      ("For thin strips a hard sear is usually fine, but %dF (%dC) removes the guesswork."
                       % (min_f, int((min_f - 32) * 5 / 9))))
        elif stated and not unsafe:
            strengths.append("The cooking temperature for the %s is stated." % label)
        if needs_rest and not re.search(r"\brest\w*\b", text_low) and not thin_cut:
            F.add("rest_missing", "medium", "technique",
                  "No rest step for %s" % label,
                  "", "Cutting straight into the meat dumps the juice on the board and dries the rest of it out.",
                  "Rest it before slicing (%s), and add that to the total time."
                  % ("10-15 minutes for steaks and chops" if key in ("steak", "pork chop") else "15-20 minutes"))
        elif re.search(r"\brest\w*\b", text_low):
            strengths.append("The protein gets a rest step.")
        if key in ("steak", "beef"):
            th = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|\s)?\s*(?:inch|in\b|inches)", norm_text)
            per_side = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)?\s*minutes?\s*(?:per side|each side|a side)", norm_text)
            if th and per_side:
                thick = float(th.group(1))
                need = 2.0 if thick <= 0.5 else 2.5 if thick <= 0.75 else 3.0 if thick <= 1.0 else 3.5 if thick <= 1.25 else 4.0 if thick <= 1.5 else 4.5 if thick <= 1.75 else 5.0
                stated_per = float(per_side.group(2) or per_side.group(1))
                if stated_per < need - 0.6:
                    F.add("steak_time_thickness", "high", "technique",
                          "A %s thick steak seared for %s per side is not enough" % (th.group(1), per_side.group(0)),
                          per_side.group(0),
                          "Cook time follows thickness, not the timer. A %s steak needs about %s per side."
                          % (th.group(1), need),
                          "Sear %s per side for a medium-rare centre, then confirm with a probe." % need)
        if key in ("chicken breast",):
            m = re.search(r"(\d+)\s*(?:-|to)?\s*(\d+)?\s*minutes?", norm_text)
            if m and not re.search(r"\b(butterf|flatten|thin|pound|thinly)\b", text_low):
                hi = int(m.group(2) or m.group(1))
                if hi <= 22:
                    F.add("chicken_thickness", "medium", "technique",
                          "Chicken breasts cooked in %d minutes will be raw in the middle" % hi,
                          m.group(0),
                          "An unflattened breast is 1.5-2 inches thick. 20 minutes only works if you pound it thin.",
                          "Butterfly or pound the breasts to 3/4 inch and cook 12-14 minutes per side, or keep 25-30 minutes and check the temperature.")
    if re.search(r"\brinse\b", text_low) and re.search(r"\b(chicken|poultry|turkey|duck|pork|beef)\b", text_low):
        F.add("rinse_meat", "high", "technique",
              "The recipe says to rinse raw meat",
              "rinse", "Rinsing raw poultry spreads bacteria across the sink and the counter.",
              "Delete the rinse step. Pat the meat dry with paper towel instead - a dry surface is what browning needs.")

    # ---------------- technique rules ----------------
    has_sear = bool(re.search(r"\b(sear|brown|saut\w+)\b", text_low))
    pan_heated = bool(re.search(
        r"\b(preheat|hot pan|until hot|hot skillet|heated|heat the (oil|pan)|heat oil)\b", text_low))
    if has_sear and not pan_heated:
        F.add("cold_pan", "high", "technique",
              "Searing without a hot pan",
              "", "A cold pan releases the meat instead of searing it; you get grey, steamed, stuck protein.",
              "Heat the pan until a drop of water sizzles and evaporates (about 3-4 minutes) before the oil goes in.")
    elif has_sear:
        strengths.append("The pan is heated before searing.")

    recipe_uses_pot = bool(re.search(
        r"\b(dutch oven|stockpot|large pot|heavy pot|roasting pan|casserole dish|slow cooker)\b", text_low))
    for s in steps:
        if re.search(r"\b(sear|saute|saut\w+|brown)\w*\b", s["text"].lower()):
            step_low = s["text"].lower()
            big_vessel = bool(re.search(r"\b(pot|dutch oven|roasting pan|casserole dish|sheet pan|stockpot)\b", step_low))
            lbs = 0.0
            count = 0.0
            for i in ings:
                if re.search(r"\b(chicken|beef|pork|turkey|steak|shrimp|salmon|fish|lamb)\b", i["name"].lower()):
                    if i["unit"] == "lb" and i["qty"]:
                        lbs += i["qty"]
                    if i["unit"] in ("piece", "breast", "thigh", "fillet") and i["qty"]:
                        count += i["qty"]
            if not big_vessel and not recipe_uses_pot and lbs >= 1.25:
                F.add("pan_crowding", "high", "technique",
                      "Searing about %s lb of meat in one pan" % fmt_qty(lbs),
                      s["text"][:120],
                      "A crowded pan drops below searing temperature and steams the food instead of browning it.",
                      "Brown in batches so the pieces never touch, and add 5-10 minutes per extra batch.")
            elif not big_vessel and not recipe_uses_pot and count > 4:
                F.add("pan_crowding", "medium", "technique",
                      "Searing %s pieces at once" % fmt_qty(count),
                      s["text"][:120],
                      "More than about four pieces in a skillet means the temperature crashes and nothing browns.",
                      "Do them in two batches.")
            break

    if re.search(r"\bhigh heat\b", text_low) and re.search(r"\b(olive oil|extra virgin)\b", ing_text):
        F.add("oil_smoke", "medium", "technique",
              "Extra virgin olive oil on high heat for searing",
              "", "EVOO starts smoking around 375-405F. Once it smokes it turns bitter and the food tastes acrid.",
              "Use an oil with a higher smoke point (avocado, canola, grapeseed) for the sear and keep the EVOO for finishing.")
    if re.search(r"\bhigh heat\b", text_low) and re.search(r"\bbutter\b", ing_text) and re.search(r"\b(sear|brown)\b", text_low):
        F.add("butter_burn", "medium", "technique",
              "Butter on high heat for searing",
              "", "Butter burns at around 350F, so it goes black before the meat browns.",
              "Use clarified butter or ghee, or sear in oil and add the butter at the end.")

    for s in steps:
        t = s.get("oven_temp_f")
        if not t:
            continue
        low = s["text"].lower()
        for food, (lo, hi) in OVEN_BANDS.items():
            if food in low or food in recipe["title"].lower():
                if not (lo - 5 <= t <= hi + 5):
                    F.add("oven_temp_band", "medium", "technique",
                          "%dF is outside the usual %d-%dF range for %s" % (t, lo, hi, food),
                          s["text"][:120],
                          "Baking %s at the wrong temperature either burns the outside or leaves the middle raw." % food,
                          "Use %d-%dF for %s." % (lo, hi, food))
                break
    if re.search(r"\b(custard|custards|creme brulee)\b", text_low):
        oven_temps = [s.get("oven_temp_f") for s in steps if s.get("oven_temp_f")]
        if oven_temps and max(oven_temps) > 340 and not re.search(r"\bwater bath\b", text_low):
            F.add("custard_hot", "medium", "technique",
                  "Custard baked above 340F",
                  "", "Hot custards go rubbery and the top sets before the middle does.",
                  "Drop to 300-325F and bake in a water bath if you want a smooth texture.")

    if re.search(r"\b(pie|pastry|tart)\b", text_low) and re.search(r"\b(filling|crust)\b", text_low):
        if not re.search(r"\b(pre[- ]?bake|blind[- ]?bake)\b", text_low) and not re.search(r"\bchill\w*\b.*\b(dough|crust)\b", text_low):
            F.add("pie_prebake", "medium", "technique",
                  "The pastry crust is never pre-baked",
                  "", "An unbaked shell under a wet filling turns to soggy paste.",
                  "Blind-bake the crust for 15-20 minutes until dry, then fill.")
    if re.search(r"\b(pizza dough|bread dough|yeast)\b", text_low) and not re.search(r"\brest\w*\b", text_low):
        F.add("dough_rest", "medium", "technique",
              "Yeast dough is never rested",
              "", "Dough that goes straight into a hot oven springs unevenly and tears.",
              "Rest the dough 30-60 minutes at room temperature (or overnight in the fridge) before shaping.")

    if re.search(r"\bdeep[- ]?fry", text_low):
        fry_temps = [int(x) for x in re.findall(r"(\d{3})\s*(?:\u00b0|degrees?)?\s*F(?![A-Za-z])", full_text)]
        if not any(320 <= t <= 380 for t in fry_temps):
            F.add("fry_temp_missing", "high", "technique",
                  "Deep frying with no oil temperature",
                  "", "Without a thermometer in the oil, deep-fried food is greasy outside and raw inside.",
                  "Heat the oil to 350F (175C) and hold it there between batches.")

    if re.search(r"\b(pasta|spaghetti|penne|linguine|noodles)\b", ing_text + text_low):
        m = re.search(r"(?:cook|boil)\w*\s+(?:the\s+)?\w*\s*(?:for\s+)?(\d+)\s*(?:-|to)?\s*(\d+)?\s*minutes?", norm_text)
        if m:
            hi = int(m.group(2) or m.group(1))
            if hi < 8 and not re.search(r"\b(al dente|fresh|gluten[- ]free)\b", text_low):
                F.add("pasta_time", "medium", "technique",
                      "Pasta cooked for only %d minutes" % hi,
                      m.group(0),
                      "Dried pasta needs 9-14 minutes in well-salted boiling water. Under-cooked pasta turns to glue in the sauce.",
                      "Start the timer when the water returns to a boil and taste from minute 9.")
        if not re.search(r"\bsalt\w*\b", text_low) and re.search(r"\bwater\b", text_low):
            F.add("pasta_water", "low", "technique",
                  "The pasta water is never salted",
                  "", "The pasta water seasons the sauce and helps the starch bind to it.",
                  "Salt the water to about 1 tablespoon per quart.")

    rice_water = {}
    for i in ings:
        if re.search(r"\b(rice)\b", i["name"].lower()) and i["unit"] == "cup" and i["qty"]:
            rice_water["rice"] = i["qty"]
        if i["name"].lower().strip() in ("water", "stock", "broth") and i["unit"] == "cup" and i["qty"]:
            rice_water["water"] = i["qty"]
    if "rice" in rice_water and "water" in rice_water:
        ratio = rice_water["water"] / rice_water["rice"]
        lower = recipe["title"].lower() + " " + ing_text
        if re.search(r"\b(basmati|sushi|jasmine|short[- ]grain)\b", lower):
            want = (1.25, 1.75)
        elif re.search(r"\b(brown|wild)\b", lower):
            want = (2.2, 3.2)
        else:
            want = (1.8, 2.3)
        if not (want[0] - 0.15 <= ratio <= want[1] + 0.15):
            F.add("rice_ratio", "medium", "technique",
                  "Water to rice is about %.1f to 1" % ratio,
                  "rice %s / water %s" % (fmt_qty(rice_water["rice"]), fmt_qty(rice_water["water"])),
                  "Off-ratio water is the number one reason rice comes out dry or gluey.",
                  "Use about %.1f cups of water per cup of rice for this style." % ((want[0] + want[1]) / 2))

    if protein_hits and not re.search(r"\bsalt\w*\b", ing_text):
        F.add("no_salt", "medium", "technique",
              "No salt in a savoury recipe with meat",
              "", "Unsalted food tastes flat no matter how long it cooks.",
              "Season in layers - at the start of the cook and again at the end, tasting as you go.")
    if re.search(r"\b(braise|stew|chili|casserole)\b", text_low) and not re.search(r"\b(vinegar|lemon|lime|tomato paste|citrus)\b", ing_text):
        F.add("no_acid", "low", "technique",
              "A long braise with no acid",
              "", "Acid is what stops a long braise from tasting heavy and flat.",
              "Add a splash of vinegar, lemon juice or tomato paste near the end.")

    if re.search(r"\bfrozen\b", ing_text) and not re.search(r"\b(thaw|defrost)\b", text_low):
        F.add("thaw_missing", "high", "completeness",
              "Frozen ingredients with no thawing step",
              "", "Cooking from frozen means the outside burns while the middle is still ice.",
              "Move the frozen items to the fridge the night before (or thaw in cold water for 30 minutes per pound).")
    if re.search(r"\bfrozen\b", ing_text) and re.search(r"\broom temperature\b", text_low):
        F.add("frozen_contradiction", "medium", "completeness",
              "A frozen ingredient used at room temperature",
              "", "Frozen dough, butter or pastry will not behave as written.",
              "Thaw first, or change the ingredient to something fresh.")

    if re.search(r"\bleftovers?\b", text_low) and not re.search(r"\b(cool\w*|within\s+\w+\s+hours?)\b", text_low):
        F.add("leftover_cooling", "low", "technique",
              "Leftovers go straight in the fridge with no cooling step",
              "", "Putting a steaming pot in the fridge keeps it in the food safety danger zone for hours.",
              "Cool it on the counter for no more than 2 hours, then refrigerate.")

    if re.search(r"\b(bake|baked)\b", text_low) and re.search(r"\bserve\w*\b.{0,30}\b(warm|immediately|right away)\b", text_low) \
            and not re.search(r"\bcool\w*\b", text_low):
        F.add("no_cooling", "low", "technique",
              "Baked goods are served without cooling",
              "", "Cutting a cake or brownies straight out of the oven makes them gummy and tear apart.",
              "Cool on a rack for 20-30 minutes (1-2 hours for a tall cake) before slicing.")
    if re.search(r"\bcookie\w*\b", (recipe["title"] + " " + text_low).lower()):
        bake_minutes = 0
        for s in steps:
            if s.get("duration") and s["station"] == "oven":
                bake_minutes = max(bake_minutes, s["duration"])
        if bake_minutes >= 20 and not re.search(r"\b(rotate|halfway|half way|swap)\b", text_low):
            F.add("no_pan_rotation", "low", "technique",
                  "A %s bake with no instruction to rotate the pans" % fmt_clock(bake_minutes),
                  "", "One tray browns faster than the next. Cookies need turning halfway or half of them burn.",
                  "Add 'Rotate the pans halfway through the bake'.")

    servings = recipe["servings"]
    protein_lb = 0.0
    veg_found = False
    for i in ings:
        if re.search(r"\b(chicken|beef|pork|turkey|lamb|fish|salmon|shrimp)\b", i["name"].lower()):
            if i["unit"] == "lb" and i["qty"]:
                protein_lb += i["qty"]
        if re.search(r"\b(lettuce|spinach|kale|broccoli|carrot|onion|pepper|zucchini|mushroom|tomato|potato|peas|corn|asparagus|cabbage|cauliflower|eggplant|cucumber|squash|green bean)\b", i["name"].lower()):
            veg_found = True
    if servings and protein_lb:
        per = protein_lb / servings
        if per < 0.25:
            F.add("light_protein", "low", "completeness",
                  "About %s oz of protein per serving" % fmt_qty(per * 16),
                  "", "That is a light portion for a main course - people will leave hungry.",
                  "Raise the protein to about 4-6 oz per serving, or make it a starter with bread.")
        elif per > 0.9:
            F.add("heavy_protein", "low", "completeness",
                  "About %s oz of protein per serving" % fmt_qty(per * 16),
                  "", "That is a lot of protein for one sitting, and it will crowd the pan.",
                  "Check the quantity - that is usually a doubling mistake.")
    if servings and not veg_found and protein_hits:
        F.add("no_veg", "low", "completeness",
              "No vegetables in the ingredient list",
              "", "A meat-only main course with no vegetable is unbalanced on the plate.",
              "Add a vegetable side, or stir greens into the pan at the end.")

    # ---------------- equipment ----------------
    gear_text = (ctx.get("gear") or "").lower()
    used_tools = []
    for tool, kws, workaround in EQUIPMENT:
        for kw in kws:
            if kw in norm_text:
                used_tools.append((tool, workaround))
                break
    missing_tools = []
    if gear_text.strip():
        for tool, workaround in used_tools:
            aliases = GEAR_ALIASES.get(tool, [tool])
            if not any(a in gear_text for a in aliases):
                missing_tools.append((tool, workaround))
        for tool, workaround in missing_tools:
            sev = "high" if tool in CRITICAL_TOOLS else "medium"
            F.add("equipment_missing", sev, "equipment",
                  "You need a %s" % tool,
                  tool,
                  "This recipe calls for equipment that is not on your kit list.",
                  workaround)
    else:
        strengths.append("No kit list given, so equipment gaps were skipped.")

    # ---------------- scaling ----------------
    scale = {"factor": 1.0, "target": None, "warnings": [], "ingredients": [], "note": ""}
    target = ctx.get("target_servings")
    if target and not servings:
        scale["note"] = "The recipe does not state a serving count, so quantities were not rescaled."
    elif servings and target and target > 0:
        factor = target / servings
        scale["factor"] = round(factor, 2)
        scale["target"] = target
        for i in ings:
            q = i["qty"]
            newq = round(q * factor, 3) if q is not None else None
            scale["ingredients"].append({
                "raw": i["raw"], "name": i["name"], "unit": i["unit"],
                "qty": q, "scaled_qty": newq,
                "scaled": ("%s %s %s" % (fmt_qty(newq), i["unit"] or "", i["name"])).strip() if newq is not None else i["raw"],
            })
        if factor > 1.4:
            scale["warnings"].append(
                "At %sx the oven temperature stays the same, but cook time rises about 20-25%% for a single pan. Bake in batches if you can."
                % fmt_qty(factor))
            scale["warnings"].append(
                "Scale salt and strong spices by about 1.5x, not %sx - doubling them makes the dish inedible." % fmt_qty(factor))
        if factor < 0.8:
            scale["warnings"].append(
                "At %sx the cook time only drops about 10%%. Small batches catch fast, so watch it."
                % fmt_qty(factor))
        if re.search(r"\b(cake|casserole|lasagna|souffle)\b", recipe["title"].lower()):
            scale["warnings"].append("A scaled-up cake or casserole needs a second pan - one pan cannot hold double the batter.")
        if re.search(r"\b(cookie|cookies|tray|sheet pan)\b", (recipe["title"] + " " + ing_text).lower()):
            scale["warnings"].append("Double batches of cookies need a second sheet pan, or they bake in two rounds.")

    if ctx.get("time_available") and total_min:
        avail = float(ctx["time_available"])
        if total_min > avail:
            F.add("time_budget", "high", "timing",
                  "You need about %s but only have %s" % (fmt_clock(total_min), fmt_clock(avail)),
                  "", "Starting this in the window you have means something is raw when you sit down.",
                  "Start the long step %s earlier, use the make-ahead list, or pick a different night."
                  % fmt_clock(total_min - avail))
        else:
            strengths.append("It fits your %s window with %s to spare." % (fmt_clock(avail), fmt_clock(avail - total_min)))

    make_ahead = []
    for s in steps:
        low = s["text"].lower()
        if re.search(r"\b(marinat\w+|chill\w*|refrigerat\w+|freeze\w*|brin\w+|soak\w*|rise\w*|proof\w*)\b", low):
            make_ahead.append({"step": s["index"], "text": s["text"], "when": "the day before"})
    if make_ahead:
        strengths.append("%d step(s) can move to the day before." % len(make_ahead))

    # ---------------- scoring ----------------
    weights = INTENT_WEIGHTS[ctx["intent"]]
    axis_scores = {}
    for axis in AXES:
        penalty = sum(SEVERITY_POINTS.get(f["severity"], 4) for f in F.items if f["axis"] == axis)
        axis_scores[axis] = max(0.0, 100.0 - penalty)
    caps = []
    if F.count("critical") >= 1:
        axis_scores["technique"] = min(axis_scores["technique"], 45)
        caps.append("A critical safety finding caps the technique axis at 45.")
    if F.count("critical") >= 2:
        axis_scores["technique"] = min(axis_scores["technique"], 32)
    if not ings:
        axis_scores["completeness"] = min(axis_scores["completeness"], 40)
        caps.append("No ingredient list caps completeness at 40.")
    if not recipe["claimed_minutes"] and time_coverage < 0.5:
        axis_scores["timing"] = min(axis_scores["timing"], 45)
        caps.append("Almost no step timings caps timing at 45.")
    if any(t in CRITICAL_TOOLS for t, _ in missing_tools):
        axis_scores["equipment"] = min(axis_scores["equipment"], 50)
        caps.append("Missing a core piece of equipment caps equipment fit at 50.")

    weighted = sum(axis_scores[a] * weights[a] for a in AXES)
    overall = weighted - 0.6 * F.total_points()
    if F.count("critical") >= 1:
        overall = min(overall, 45.0)
        caps.append("A critical safety finding caps the overall score at 45.")
    if F.count("high") >= 2:
        overall = min(overall, 60.0)
        caps.append("Two or more high-priority findings cap the overall score at 60.")
    if F.has("internal_temp_missing"):
        overall = min(overall, 65.0)
        caps.append("No internal temperature caps the score at 65 - you cannot verify the food is safe.")
    if F.has("rinse_meat"):
        overall = min(overall, 65.0)
        caps.append("A food hygiene problem caps the score at 65.")
    if any(i["id"] == "ingredient_unlisted" and i["severity"] == "high" for i in F.items):
        overall = min(overall, 55.0)
        caps.append("An ingredient used but never listed caps the score at 55.")
    overall = float(max(0.0, min(98.0, round(float(overall), 1))))

    verdict = "needs_rework"
    verdict_label = "Needs rework"
    for threshold, key, label in VERDICTS:
        if overall >= threshold:
            verdict, verdict_label = key, label
            break

    fix_plan = []
    for f in sorted(F.items, key=lambda x: (SEVERITY_ORDER[x["severity"]], -x["gain"])):
        fix_plan.append({
            "id": f["id"], "severity": f["severity"], "title": f["title"],
            "fix": f["fix"], "gain": f["gain"], "axis": f["axis"],
        })

    summary_bits = []
    if total_min:
        summary_bits.append("%s end to end (%s hands-on)" % (fmt_clock(total_min), fmt_clock(hands_on)))
    if claimed and total_min and abs(claimed - total_min) > 10:
        summary_bits.append("the headline says %s" % fmt_clock(claimed))
    if F.count("critical"):
        summary_bits.append("%d critical safety problem(s)" % F.count("critical"))
    elif F.count("high"):
        summary_bits.append("%d high-priority fix(es)" % F.count("high"))
    else:
        summary_bits.append("no high-priority fixes")
    summary = "%s: %s." % (recipe["title"], "; ".join(summary_bits))

    return _finalize(recipe, ctx, F, strengths, timeline, overall, total_min, hands_on,
                     scale, axis_scores=axis_scores, weights=weights, verdict=verdict,
                     verdict_label=verdict_label, make_ahead=make_ahead, used_tools=used_tools,
                     missing_tools=missing_tools, caps=caps, summary=summary,
                     serial_sum=serial_sum, savings=savings, claimed=claimed,
                     fix_plan=fix_plan, untimed_active=untimed_active)


def _finalize(recipe, ctx, F, strengths, timeline, overall, total_min, hands_on, scale,
              axis_scores=None, weights=None, verdict=None, verdict_label=None,
              make_ahead=None, used_tools=None, missing_tools=None, caps=None,
              summary=None, serial_sum=None, savings=None, claimed=None, fix_plan=None,
              untimed_active=0):
    axis_scores = axis_scores or dict((a, 0) for a in AXES)
    weights = weights or INTENT_WEIGHTS["balanced"]
    return {
        "title": recipe["title"],
        "servings": recipe["servings"],
        "yield_text": recipe.get("yield_text", ""),
        "claimed_minutes": claimed if claimed is not None else recipe["claimed_minutes"],
        "computed": {
            "total_minutes": total_min,
            "hands_on_minutes": hands_on,
            "passive_minutes": round((total_min or 0) - (hands_on or 0), 1),
            "serial_minutes": serial_sum,
            "overlap_savings": savings,
            "steps": len(recipe["steps"]),
            "timed_steps": sum(1 for s in recipe["steps"] if s["duration"]),
            "untimed_active_steps": untimed_active,
        },
        "score": overall,
        "verdict": verdict or "needs_rework",
        "verdict_label": verdict_label or "Needs rework",
        "axes": [{"axis": a, "score": round(axis_scores[a], 1), "weight": weights[a]} for a in AXES],
        "findings": sorted(F.items, key=lambda x: (SEVERITY_ORDER[x["severity"]], x["axis"])),
        "strengths": strengths,
        "timeline": timeline,
        "ingredients": recipe["ingredients"],
        "scale": scale,
        "make_ahead": make_ahead or [],
        "equipment_needed": [{"tool": t, "workaround": w} for t, w in (used_tools or [])],
        "equipment_missing": [{"tool": t, "workaround": w} for t, w in (missing_tools or [])],
        "fix_plan": fix_plan or [],
        "caps": caps or [],
        "summary": summary or recipe["title"],
        "context": ctx,
        "notes": recipe["notes"],
    }


def export_markdown(result):
    lines = []
    lines.append("# cook-forge: %s" % result["title"])
    lines.append("")
    lines.append("**Score:** %s/100 - %s" % (result["score"], result["verdict_label"]))
    if result.get("servings"):
        lines.append("**Serves:** %s" % fmt_qty(result["servings"]))
    if result.get("yield_text"):
        lines.append("**Yield:** %s" % result["yield_text"])
    comp = result.get("computed") or {}
    if comp.get("total_minutes"):
        extra = ", recipe claims %s" % fmt_clock(result["claimed_minutes"]) if result.get("claimed_minutes") else ""
        lines.append("**Time:** %s total, %s hands-on%s" % (
            fmt_clock(comp["total_minutes"]), fmt_clock(comp["hands_on_minutes"]), extra))
    lines.append("")
    lines.append("## Axes")
    for a in result["axes"]:
        lines.append("- **%s**: %s/100 (weight %s)" % (a["axis"], a["score"], a["weight"]))
    lines.append("")
    lines.append("## Timeline")
    for row in result.get("timeline", []):
        lines.append("- %s to %s [%s] %s" % (fmt_clock(row["start"]), fmt_clock(row["end"]),
                                             row["station"], row["text"]))
    lines.append("")
    lines.append("## Findings")
    if not result["findings"]:
        lines.append("Nothing flagged.")
    for f in result["findings"]:
        lines.append("### [%s] %s (%s)" % (f["severity"].upper(), f["title"], f["axis"]))
        if f.get("evidence"):
            lines.append("> %s" % f["evidence"])
        lines.append("**Why:** %s" % f["why"])
        lines.append("**Fix:** %s" % f["fix"])
        lines.append("")
    lines.append("## Fix plan")
    for i, fx in enumerate(result.get("fix_plan", []), 1):
        lines.append("%d. [%s] %s - %s (+~%s points)" % (i, fx["severity"], fx["title"], fx["fix"], fx["gain"]))
    lines.append("")
    if result.get("strengths"):
        lines.append("## What is already good")
        for s in result["strengths"]:
            lines.append("- %s" % s)
    lines.append("")
    if result.get("make_ahead"):
        lines.append("## Make ahead")
        for m in result["make_ahead"]:
            lines.append("- Step %s (%s): %s" % (m["step"], m["when"], m["text"]))
    return "\n".join(lines)


def to_json(result):
    return json.dumps(result, indent=2, default=str)
