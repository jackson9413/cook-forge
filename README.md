# cook-forge

**Local-first recipe technique and timing analyser.**

Paste a recipe. cook-forge rebuilds the real clock from the steps, flags the technique
problems you are going to hit in the kitchen, checks the food safety gaps, and hands back
a fix plan you can cook from.

No API keys. No network calls. No LLM. Your recipes never leave your machine.

---

## Why it matters

Almost every recipe is wrong in one of four ways, and you only find out at 7pm:

1. **The headline time is a lie.** "30 minutes" hides a 44 minute cook.
2. **The steps are written as a straight line.** The oven sits empty while you chop, and
   you wait with nothing to do while the oven is on.
3. **The technique is under-specified.** No internal temperature, no preheat, a crowded
   pan, a marinade that never had time to work.
4. **The kit does not match.** The recipe wants a wok, a probe thermometer and a Dutch
   oven, and you have one of them.

cook-forge reads the recipe the way an experienced cook reads it, then tells you what
changes.

---

## What it does

**A real timeline, not a sum.** Every step is parsed for duration, heat, station and
whether it needs your hands. cook-forge schedules them the way a cook actually runs
them: steps execute in order, an unattended step (bake, simmer, chill) releases you but
still occupies its station, and the next hands-on step overlaps with it. You get an
end-to-end time, a hands-on time, and the overlap you are missing.

**Food safety, checked separately.** Internal temperatures (poultry 165F, ground meat
160F, whole cuts 145F), unsafe target temperatures, raw-meat rinsing, chilling and
resting, pan crowding, oil smoke points, deep-fry oil temperature, blind baking, water
baths, dough rest.

**Technique and sequencing.** Preheat before use (and before the first thing goes in the
oven), oven temperature bands per food, butter and olive oil at searing heat, rice water
ratios, pasta timing, steak thickness against cook time, chicken breast thickness,
acidity in a braise, seasoning.

**Your kitchen.** Give it your kit list and it flags the missing pieces, with a
workaround for each. Intent (weeknight / showstopper / beginner / batch / entertaining)
re-weights the scorecard. Give it the minutes you actually have and it tells you when
the dish will not fit.

**Scaling that respects cooking physics.** Double the servings and the oven temperature
does not change, the cook time rises about 20-25% for a single pan, and salt scales by
about 1.5x, not 2x.

**Make-ahead.** Chills, marinades, soaks and brines are pulled out of the cook and moved
to the day before.

---

## The scorecard

Five axes, each 0-100, weighted by intent:

| Axis | What it measures |
|---|---|
| **timing** | Do the steps add up? Is the headline honest? Can the passive steps overlap? |
| **technique** | Will the food actually brown, set, tenderise and reach temperature? |
| **sequencing** | Is the order right? Does the preheat come first? Is the wait at the end? |
| **completeness** | Does every ingredient get used? Is everything used also listed? Missing rests, thawing, chilling? |
| **equipment** | Can you make this with the kit you said you have? |

Score bands: **85+** ready to cook, **70-84** mostly ready, **55-69** needs tweaks,
**40-54** tight but usable, **under 40** needs rework.

Structural caps stop a recipe from scoring well by skipping the hard part: a critical
food safety finding caps the score at 45, two or more high-priority findings cap it at
60, a missing internal temperature caps it at 65, and an ingredient used but never
listed caps it at 55.

Every finding carries the evidence that triggered it, why it matters, and a concrete fix,
plus an estimated score gain.

---

## Run it

~~~bash
cd cook-forge
python3 -m pip install -r requirements.txt
python3 app.py
~~~

Then open **http://127.0.0.1:5057**.

Or in one step:

~~~bash
./run.sh
~~~

Set PORT to use a different port. Set COOKFORGE_DB to move the SQLite file.

### Tests

~~~bash
python3 -m unittest discover -s tests -v
~~~

50 tests covering the parser, the timeline scheduler, every rule family, the scoring
caps, the exports and the REST API.

---

## Tech stack

- **Backend:** Python 3, Flask, SQLite. The analysis engine (engine.py) is pure
  standard library - no pandas, no numpy, no model calls.
- **Frontend:** vanilla HTML/CSS/JS, no build step, no framework, no CDN.
- **Storage:** one SQLite file (data/cookforge.db) with a run log, 1-5 star
  self-rating and notes.
- **Dependencies:** Flask only.

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/health | Liveness check |
| GET | /api/samples | Built-in sample recipes |
| GET | /api/sample?id=chili | One sample recipe |
| POST | /api/analyze | Analyse a recipe |
| GET | /api/sessions | Run history |
| GET | /api/sessions/<id> | One saved run |
| PATCH | /api/sessions/<id> | Save a rating and notes |
| GET | /api/export/<id>?fmt=md or json | Export a run |

POST /api/analyze body:

~~~json
{
  "recipe": "Title: ...",
  "gear": "oven, cast iron skillet, probe thermometer",
  "intent": "weeknight",
  "target_servings": 6,
  "time_available": 45
}
~~~

---

## Built-in samples

Five recipes ship with the tool, three of them deliberately flawed so you can see what
a finding looks like: a clean sheet-pan salmon, a solid beef chili, a roast chicken that
lies about its time, a cookie recipe that never lists the butter, and a stir-fry that
crowds the pan.

---

## How the engine reads a recipe

- Header lines (Title:, Serves:, Time:, Equipment:) are read when present, but
  everything works without them.
- Ingredient quantities handle unicode fractions, mixed fractions, decimals and about
  thirty unit names.
- Durations handle seconds, minutes, hours, ranges, and compound headers such as
  "1 hour 15 minutes".
- Oven temperatures are read in F or C and converted; gas marks are mapped.
- Steps are classified by station (oven, stovetop, fridge, prep) and by whether they
  need your hands.

If a recipe has no headers at all, cook-forge falls back to detecting bullet lists as
ingredients and numbered lines as steps.

---

## Limitations, honestly

- It cannot tell you if your oven is actually 200F, or if your wok is big enough.
- Ingredient matching is keyword based; it will occasionally miss a synonym.
- It has no idea what your pantry already holds.
- The 2-minute estimate for untimed hands-on steps is an estimate, and it says so in the
  timeline.

---

## License

MIT.
