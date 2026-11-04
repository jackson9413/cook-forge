# -*- coding: utf-8 -*-
"""Smoke tests for cook-forge. Run: python3 -m unittest discover -s tests -v"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import engine  # noqa: E402
import samples  # noqa: E402

GOOD = """Title: Test Salmon
Serves: 2
Time: 30 minutes

Ingredients:
- 1 lb salmon fillet
- 1 tsp salt
- 1 tbsp olive oil
- 1 lemon

Steps:
1. Preheat the oven to 425F.
2. Pat the salmon dry and rub it with oil and salt.
3. Roast the salmon for 10 to 12 minutes, until it reaches 145F in the thickest part.
4. Rest the salmon for 5 minutes before serving.
"""

BAD = """Title: Bad Chicken
Serves: 4
Time: 30 minutes

Ingredients:
- 4 lb whole chicken
- 2 tbsp butter
- 1 tsp salt

Steps:
1. Rinse the chicken and pat it dry.
2. Marinate the chicken for 15 minutes.
3. Put the chicken in a roasting pan.
4. Roast the chicken for 20 minutes.
5. Rest the chicken for 5 minutes and carve it.
"""


def ids(result):
    return set(f["id"] for f in result["findings"])


class TestParsing(unittest.TestCase):
    def test_header_parsing(self):
        r = engine.parse_recipe(GOOD)
        self.assertEqual(r["title"], "Test Salmon")
        self.assertEqual(r["servings"], 2.0)
        self.assertEqual(r["claimed_minutes"], 30.0)
        self.assertEqual(len(r["steps"]), 4)
        self.assertEqual(len(r["ingredients"]), 4)

    def test_compound_time_header_is_summed(self):
        text = "Title: X\nTime: 1 hour 15 minutes\n\nSteps:\n1. Cook it for 5 minutes.\n"
        r = engine.parse_recipe(text)
        self.assertEqual(r["claimed_minutes"], 75.0)

    def test_fraction_and_units(self):
        r = engine.parse_recipe("Ingredients:\n- 1 1/2 cups flour\n- 2 tbsp oil\n- 3 cloves garlic\n")
        self.assertAlmostEqual(r["ingredients"][0]["qty"], 1.5)
        self.assertEqual(r["ingredients"][0]["unit"], "cup")
        self.assertEqual(r["ingredients"][1]["unit"], "tbsp")
        self.assertEqual(r["ingredients"][2]["qty"], 3)

    def test_decimal_quantity_not_mangled(self):
        r = engine.parse_recipe("Ingredients:\n- 1.5 lb flank steak\n")
        self.assertAlmostEqual(r["ingredients"][0]["qty"], 1.5)
        self.assertEqual(r["ingredients"][0]["unit"], "lb")

    def test_unicode_fractions(self):
        qty, rest = engine.parse_qty(engine.normalize_numbers("1 \u00bd cups"))
        self.assertAlmostEqual(qty, 1.5)
        self.assertEqual(rest, "cups")

    def test_cookie_yield_is_not_servings(self):
        r = engine.parse_recipe("Title: Cookies\nMakes: 24 cookies\n\nSteps:\n1. Bake for 12 minutes.\n")
        self.assertIsNone(r["servings"])
        self.assertIn("24 cookies", r["yield_text"])

    def test_oven_temp_fahrenheit_without_space(self):
        r = engine.parse_recipe("Steps:\n1. Preheat the oven to 425F.\n2. Bake for 20 minutes.\n")
        self.assertEqual(r["steps"][0]["oven_temp_f"], 425)

    def test_celsius_converted(self):
        r = engine.parse_recipe("Steps:\n1. Preheat the oven to 200C.\n2. Bake for 40 minutes.\n")
        self.assertEqual(r["steps"][0]["oven_temp_c"], 200)
        self.assertIsNone(r["steps"][0]["oven_temp_f"])


class TestTimeline(unittest.TestCase):
    def test_steps_run_in_order(self):
        r = engine.analyze(BAD)
        rows = r["timeline"]
        for i in range(1, len(rows)):
            self.assertGreaterEqual(rows[i]["start"], rows[i - 1]["start"])

    def test_passive_step_releases_the_cook(self):
        r = engine.analyze(GOOD)
        rows = r["timeline"]
        roast = [x for x in rows if "Roast" in x["text"]][0]
        self.assertTrue(roast["passive"])
        self.assertGreater(r["computed"]["total_minutes"], 0)

    def test_total_exceeds_hands_on_for_a_bake(self):
        r = engine.analyze(GOOD)
        self.assertGreater(r["computed"]["total_minutes"], r["computed"]["hands_on_minutes"])

    def test_unattended_time_counts_towards_total(self):
        r = engine.analyze(BAD)
        self.assertGreaterEqual(r["computed"]["total_minutes"], 35)


class TestFindings(unittest.TestCase):
    def test_good_recipe_scores_ready(self):
        r = engine.analyze(GOOD)
        self.assertGreaterEqual(r["score"], 85)
        self.assertEqual(r["verdict"], "ready_to_cook")

    def test_bad_recipe_scores_low(self):
        r = engine.analyze(BAD)
        self.assertLess(r["score"], 45)
        self.assertEqual(r["verdict"], "needs_rework")

    def test_rinse_raw_meat_flagged(self):
        self.assertIn("rinse_meat", ids(engine.analyze(BAD)))

    def test_missing_internal_temperature_flagged(self):
        self.assertIn("internal_temp_missing", ids(engine.analyze(BAD)))

    def test_stated_temperature_clears_the_finding(self):
        self.assertNotIn("internal_temp_missing", ids(engine.analyze(GOOD)))

    def test_unsafe_temperature_is_critical(self):
        text = """Title: Chicken
Ingredients:
- 2 lb chicken breast

Steps:
1. Roast the chicken until it reaches 140F.
"""
        r = engine.analyze(text)
        crit = [f for f in r["findings"] if f["id"] == "temp_unsafe"]
        self.assertEqual(len(crit), 1)
        self.assertEqual(crit[0]["severity"], "critical")
        self.assertLessEqual(r["score"], 45)

    def test_no_preheat_flagged(self):
        self.assertIn("no_preheat", ids(engine.analyze(BAD)))

    def test_preheat_present_is_a_strength(self):
        r = engine.analyze(GOOD)
        self.assertTrue(any("preheated" in s for s in r["strengths"]))

    def test_time_mismatch_flagged(self):
        self.assertIn("time_mismatch", ids(engine.analyze(BAD)))

    def test_marinade_too_short_flagged(self):
        self.assertIn("marinade_short", ids(engine.analyze(BAD)))

    def test_rest_too_short_for_a_whole_bird(self):
        self.assertIn("rest_short", ids(engine.analyze(BAD)))

    def test_unlisted_ingredient_flagged(self):
        text = """Title: Cookies
Makes: 12 cookies

Ingredients:
- 2 cups flour
- 1 cup sugar

Steps:
1. Preheat the oven to 350F.
2. Cream the butter and sugar together.
3. Bake for 12 minutes.
"""
        r = engine.analyze(text)
        self.assertIn("ingredient_unlisted", ids(r))

    def test_unused_ingredient_flagged(self):
        text = """Title: Soup
Serves: 4

Ingredients:
- 1 onion
- 2 tbsp olive oil
- 1 tsp smoked paprika

Steps:
1. Heat the oil in a pot.
2. Add the onion and cook for 8 minutes.
3. Simmer for 20 minutes.
"""
        r = engine.analyze(text)
        self.assertIn("ingredient_unused", ids(r))

    def test_equipment_gap_flagged(self):
        r = engine.analyze(GOOD, {"gear": "frying pan, knife"})
        self.assertIn("equipment_missing", ids(r))
        self.assertTrue(r["equipment_missing"])

    def test_no_kit_list_skips_equipment_findings(self):
        r = engine.analyze(GOOD, {"gear": ""})
        self.assertNotIn("equipment_missing", ids(r))

    def test_pan_crowding_flagged(self):
        text = """Title: Steak
Serves: 4

Ingredients:
- 3 lb flank steak
- 1 tsp salt
- 2 tbsp oil

Steps:
1. Heat the oil in a cast iron skillet over high heat.
2. Sear the steak for 3 minutes per side.
"""
        r = engine.analyze(text)
        self.assertIn("pan_crowding", ids(r))

    def test_oven_temperature_band_flagged(self):
        text = """Title: Cookies
Makes: 12 cookies

Ingredients:
- 2 cups flour
- 1 cup butter
- 1 cup sugar

Steps:
1. Preheat the oven to 450F.
2. Mix everything.
3. Bake for 12 minutes.
"""
        r = engine.analyze(text)
        self.assertIn("oven_temp_band", ids(r))

    def test_frozen_without_thaw_flagged(self):
        text = """Title: Frozen dinner
Serves: 2

Ingredients:
- 2 frozen chicken breasts
- 1 tbsp oil

Steps:
1. Heat the oil in a skillet.
2. Cook the chicken for 20 minutes.
"""
        r = engine.analyze(text)
        self.assertIn("thaw_missing", ids(r))

    def test_time_budget_overrun_flagged(self):
        r = engine.analyze(GOOD, {"time_available": 5})
        self.assertIn("time_budget", ids(r))

    def test_every_finding_has_a_fix(self):
        r = engine.analyze(BAD)
        for f in r["findings"]:
            self.assertTrue(f["fix"])
            self.assertTrue(f["why"])
            self.assertIn(f["severity"], ("critical", "high", "medium", "low"))


class TestScoring(unittest.TestCase):
    def test_score_bounds(self):
        r = engine.analyze(GOOD)
        self.assertGreaterEqual(r["score"], 0)
        self.assertLessEqual(r["score"], 100)

    def test_five_axes_present(self):
        r = engine.analyze(GOOD)
        self.assertEqual(len(r["axes"]), 5)
        self.assertEqual([a["axis"] for a in r["axes"]],
                         ["timing", "technique", "sequencing", "completeness", "equipment"])

    def test_intent_changes_weights(self):
        weeknight = engine.analyze(GOOD, {"intent": "weeknight"})
        show = engine.analyze(GOOD, {"intent": "showstopper"})
        w = dict((a["axis"], a["weight"]) for a in weeknight["axes"])
        s = dict((a["axis"], a["weight"]) for a in show["axes"])
        self.assertGreater(w["timing"], s["timing"])
        self.assertGreater(s["technique"], w["technique"])

    def test_critical_caps_score(self):
        text = """Title: Danger
Ingredients:
- 2 lb chicken breast

Steps:
1. Rinse the chicken and roast it until it reaches 130F.
"""
        r = engine.analyze(text)
        self.assertLessEqual(r["score"], 45)
        self.assertTrue(r["caps"])

    def test_scaling(self):
        r = engine.analyze(GOOD, {"target_servings": 4})
        self.assertAlmostEqual(r["scale"]["factor"], 2.0)
        self.assertTrue(r["scale"]["ingredients"])
        self.assertTrue(r["scale"]["warnings"])

    def test_no_steps_is_handled(self):
        r = engine.analyze("")
        self.assertIn("no_steps", ids(r))
        self.assertEqual(r["score"], 0)


class TestSamples(unittest.TestCase):
    def test_every_sample_analyses(self):
        for s in samples.SAMPLES:
            r = engine.analyze(s["text"], {"gear": "oven, skillet, sheet pan, wok, large pot, knife"})
            self.assertIsInstance(r["score"], float)
            self.assertTrue(r["verdict"])

    def test_calibration(self):
        ranges = {
            "sheet-pan-salmon": (85, 100),
            "chili": (80, 100),
            "roast-chicken": (10, 40),
            "cookies": (40, 70),
            "stir-fry": (50, 85),
        }
        for s in samples.SAMPLES:
            r = engine.analyze(s["text"], {"gear": "oven, skillet, sheet pan, wok, large pot, knife"})
            lo, hi = ranges[s["id"]]
            self.assertGreaterEqual(r["score"], lo, s["id"])
            self.assertLessEqual(r["score"], hi, s["id"])

    def test_bad_samples_score_below_good_ones(self):
        good = engine.analyze(samples.get_sample("sheet-pan-salmon")["text"])
        bad = engine.analyze(samples.get_sample("roast-chicken")["text"])
        self.assertGreater(good["score"], bad["score"] + 40)


class TestExports(unittest.TestCase):
    def test_markdown_export(self):
        r = engine.analyze(GOOD)
        md = engine.export_markdown(r)
        self.assertIn("# cook-forge", md)
        self.assertIn("## Timeline", md)
        self.assertIn("## Findings", md)

    def test_json_export(self):
        import json
        r = engine.analyze(GOOD)
        data = json.loads(engine.to_json(r))
        self.assertIn("score", data)
        self.assertIn("timeline", data)


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["COOKFORGE_DB"] = os.path.join(BASE_DIR, "data", "test_cookforge.db")
        import importlib
        import db as dbmod
        importlib.reload(dbmod)
        import app as appmod
        importlib.reload(appmod)
        cls.app = appmod.app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_samples_listed(self):
        r = self.client.get("/api/samples")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.get_json()), 5)

    def test_sample_fetch(self):
        r = self.client.get("/api/sample?id=chili")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Ingredients", r.get_json()["text"])

    def test_analyze_and_session(self):
        r = self.client.post("/api/analyze", json={"recipe": GOOD, "gear": "oven, sheet pan"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("score", data)
        self.assertIsNotNone(data["session_id"])

        sid = data["session_id"]
        row = self.client.get("/api/sessions/%d" % sid).get_json()
        self.assertEqual(row["title"], "Test Salmon")

        p = self.client.patch("/api/sessions/%d" % sid, json={"rating": 4, "notes": "good"})
        self.assertEqual(p.status_code, 200)
        self.assertEqual(p.get_json()["rating"], 4)

        md = self.client.get("/api/export/%d?fmt=md" % sid)
        self.assertEqual(md.status_code, 200)
        self.assertIn("cook-forge", md.get_data(as_text=True))

        js = self.client.get("/api/export/%d?fmt=json" % sid)
        self.assertEqual(js.status_code, 200)
        self.assertIn("score", js.get_data(as_text=True))

    def test_analyze_requires_recipe(self):
        r = self.client.post("/api/analyze", json={"recipe": "  "})
        self.assertEqual(r.status_code, 400)

    def test_sessions_list(self):
        r = self.client.get("/api/sessions")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json(), list)

    def test_index_served(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("cook-forge", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
