"""Integration tests for the Flask app (uses Flask's built-in test client)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import ALL_QUESTION_IDS, SYMPTOM_IDS, app


def answers(**overrides):
    """All questions answered 'no', then apply overrides."""
    base = {q: "no" for q in ALL_QUESTION_IDS}
    base.update(overrides)
    return base


class AppTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def post(self, payload):
        return self.client.post("/api/assess", json=payload)


class Pages(AppTestCase):
    def test_pages_load(self):
        for path in ("/", "/assessment", "/results"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn(b"AI Medical Diagnosis", r.data)

    def test_static_assets_load(self):
        for path in ("/static/css/style.css", "/static/js/app.js"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200, path)

    def test_disclaimer_on_pages(self):
        for path in ("/", "/assessment", "/results"):
            self.assertIn(b"educational", self.client.get(path).data.lower())

    def test_questions_endpoint(self):
        data = self.client.get("/api/questions").get_json()
        self.assertEqual(len(data["symptoms"]), 12)
        self.assertEqual(len(data["emergency_signs"]), 4)


class Validation(AppTestCase):
    def test_non_json_body(self):
        r = self.client.post("/api/assess", data="not json",
                             content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_malformed_json(self):
        r = self.client.post("/api/assess", data="{bad", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_missing_answers_key(self):
        self.assertEqual(self.post({}).status_code, 400)

    def test_answers_wrong_type(self):
        self.assertEqual(self.post({"answers": ["yes"]}).status_code, 400)

    def test_json_array_body(self):
        self.assertEqual(self.post([1, 2]).status_code, 400)

    def test_incomplete_answers(self):
        a = answers()
        del a["fever"]
        r = self.post({"answers": a})
        self.assertEqual(r.status_code, 400)
        self.assertIn("fever", " ".join(r.get_json()["details"]))

    def test_invalid_value(self):
        r = self.post({"answers": answers(fever="maybe")})
        self.assertEqual(r.status_code, 400)

    def test_unknown_question_id(self):
        a = answers()
        a["name"] = "yes"
        r = self.post({"answers": a})
        self.assertEqual(r.status_code, 400)

    def test_null_value_rejected(self):
        self.assertEqual(self.post({"answers": answers(cough=None)}).status_code, 400)

    def test_get_not_allowed_on_assess(self):
        self.assertEqual(self.client.get("/api/assess").status_code, 405)

    def test_oversized_body(self):
        r = self.client.post("/api/assess", data=json.dumps({"x": "a" * 40000}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 413)


class SuccessfulAssessment(AppTestCase):
    def test_cold_like_submission(self):
        r = self.post({"answers": answers(runny_nose="yes", sneezing="yes", sore_throat="yes")})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertFalse(data["emergency"]["triggered"])
        ids = [p["id"] for p in data["patterns"] if p["forward_supported"]]
        self.assertIn("pattern_cold_like", ids)
        cold = next(p for p in data["patterns"] if p["id"] == "pattern_cold_like")
        self.assertEqual(cold["backward_status"], "supported")
        self.assertTrue(cold["supporting_symptoms"])
        self.assertTrue(data["forward"]["trace"])
        self.assertEqual(len(data["backward"]), 3)
        self.assertTrue(all(b["trace"] for b in data["backward"]))

    def test_engines_agree_and_are_explained(self):
        data = self.post({"answers": answers(
            fever="yes", chills="yes", cough="yes", fatigue="yes")}).get_json()
        self.assertTrue(data["comparison"]["agree"])
        flu = next(p for p in data["patterns"] if p["id"] == "pattern_flu_like")
        self.assertTrue(flu["forward_supported"])
        self.assertEqual(flu["backward_status"], "supported")

    def test_no_pattern_message(self):
        data = self.post({"answers": answers()}).get_json()
        self.assertEqual(data["summary"]["supported_patterns"], 0)
        self.assertIn("No supported symptom pattern", data["summary"]["headline"])

    def test_unsure_is_kept_separate_from_no(self):
        data = self.post({"answers": answers(runny_nose="yes", sneezing="yes",
                                             sore_throat="unsure")}).get_json()
        unknown_ids = [x["id"] for x in data["answers"]["unknown"]]
        absent_ids = [x["id"] for x in data["answers"]["absent"]]
        self.assertIn("sore_throat", unknown_ids)
        self.assertNotIn("sore_throat", absent_ids)
        cold = next(p for p in data["patterns"] if p["id"] == "pattern_cold_like")
        self.assertFalse(cold["forward_supported"])
        self.assertEqual(cold["backward_status"], "inconclusive")
        self.assertIn("could not be ruled out", data["summary"]["headline"])

    def test_no_fake_scores_in_response(self):
        text = json.dumps(self.post({"answers": answers(fever="yes")}).get_json()).lower()
        for word in ("confidence", "probability", "percent", "accuracy"):
            self.assertNotIn(word, text)

    def test_response_never_confirms_disease(self):
        data = self.post({"answers": answers(fever="yes", chills="yes",
                                             cough="yes", fatigue="yes")}).get_json()
        self.assertIn("not a medical device", data["disclaimer"])
        self.assertNotIn("you have", json.dumps(data).lower())


class ResultsComeFromEngines(AppTestCase):
    """Results must follow the answers sent: supported / unsupported / inconclusive."""

    def submit(self, **kw):
        r = self.post({"answers": answers(**kw)})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        return data, {p["id"]: p for p in data["patterns"]}

    def test_supported_pattern_has_symptoms_and_rules(self):
        _, pats = self.submit(fever="yes", cough="yes", fatigue="yes")
        flu = pats["pattern_flu_like"]
        self.assertTrue(flu["forward_supported"])
        self.assertEqual(flu["backward_status"], "supported")
        labels = {s["label"] for s in flu["supporting_symptoms"]}
        self.assertEqual(labels, {"Fever", "Cough", "Unusual tiredness"})
        self.assertIn("R15", flu["rules_used"])
        self.assertNotIn("closest_rule", flu)

    def test_unsupported_pattern_reports_failed_conditions(self):
        _, pats = self.submit(fever="yes", cough="yes", fatigue="yes")
        cold = pats["pattern_cold_like"]
        self.assertFalse(cold["forward_supported"])
        self.assertEqual(cold["backward_status"], "unsupported")
        states = {c["state"] for c in cold["closest_rule"]["conditions"]}
        self.assertIn("failed", states)

    def test_inconclusive_pattern_reports_unknown_condition(self):
        _, pats = self.submit(runny_nose="yes", sore_throat="unsure")
        cold = pats["pattern_cold_like"]
        self.assertFalse(cold["forward_supported"])
        self.assertEqual(cold["backward_status"], "inconclusive")
        unknown = [c["label"] for c in cold["closest_rule"]["conditions"]
                   if c["state"] == "unknown"]
        self.assertEqual(unknown, ["Sore throat"])

    def test_forward_rule_report_present_and_complete(self):
        data, _ = self.submit(runny_nose="yes", sneezing="yes")
        report = data["forward"]["rule_report"]
        self.assertEqual(len(report), 19)
        self.assertIn("R1", {r["rule_id"] for r in report if r["fired"]})
        for entry in report:
            for c in entry["conditions"]:
                self.assertIn(c["state"], {"met", "failed", "unknown", "not_established"})

    def test_different_answers_give_different_results(self):
        _, a = self.submit(fever="yes", cough="yes", fatigue="yes")
        _, b = self.submit(sneezing="yes", itchy_eyes="yes")
        self.assertTrue(a["pattern_flu_like"]["forward_supported"])
        self.assertFalse(b["pattern_flu_like"]["forward_supported"])
        self.assertTrue(b["pattern_allergy_like"]["forward_supported"])
        self.assertFalse(a["pattern_allergy_like"]["forward_supported"])

    def test_not_sure_and_no_differ_for_same_symptom(self):
        _, with_no = self.submit(runny_nose="yes", sneezing="yes", sore_throat="no")
        _, with_unsure = self.submit(runny_nose="yes", sneezing="yes", sore_throat="unsure")
        self.assertEqual(with_no["pattern_cold_like"]["backward_status"], "unsupported")
        self.assertEqual(with_unsure["pattern_cold_like"]["backward_status"], "inconclusive")

    def test_forward_and_backward_agree(self):
        data, _ = self.submit(fever="yes", chills="yes", cough="yes", sneezing="unsure")
        self.assertTrue(data["comparison"]["agree"])


class Emergency(AppTestCase):
    def test_emergency_stays_first_even_when_a_pattern_is_supported(self):
        data = self.post({"answers": answers(
            bluish_lips="yes", fever="yes", cough="yes", fatigue="yes")}).get_json()
        self.assertTrue(data["emergency"]["triggered"])
        self.assertTrue(any(p["forward_supported"] for p in data["patterns"]))
        self.assertIn("Urgent", data["summary"]["headline"])
        self.assertNotIn("bluish_lips", data["forward"]["final_facts"])

    def test_emergency_answers_do_not_change_engine_results(self):
        plain = self.post({"answers": answers(fever="yes", cough="yes")}).get_json()
        urgent = self.post({"answers": answers(fever="yes", cough="yes",
                                               chest_pain="yes")}).get_json()
        self.assertEqual(plain["forward"]["patterns"], urgent["forward"]["patterns"])
        self.assertEqual([b["status"] for b in plain["backward"]],
                         [b["status"] for b in urgent["backward"]])

    def test_emergency_triggered_independent_of_rules(self):
        data = self.post({"answers": answers(chest_pain="yes")}).get_json()
        self.assertTrue(data["emergency"]["triggered"])
        self.assertEqual(data["emergency"]["signs"][0]["id"], "chest_pain")
        self.assertIn("Urgent", data["summary"]["headline"])
        # No symptom rule matched, yet the emergency is still reported.
        self.assertEqual(data["summary"]["supported_patterns"], 0)

    def test_emergency_not_cleared_by_pattern_match(self):
        data = self.post({"answers": answers(
            difficulty_breathing="yes", runny_nose="yes", sneezing="yes",
            sore_throat="yes")}).get_json()
        self.assertTrue(data["emergency"]["triggered"])
        self.assertIn("Urgent", data["summary"]["headline"])
        self.assertGreaterEqual(data["summary"]["supported_patterns"], 1)

    def test_emergency_signs_not_used_as_rule_facts(self):
        data = self.post({"answers": answers(chest_pain="yes")}).get_json()
        self.assertNotIn("chest_pain", data["forward"]["initial_facts"])

    def test_unsure_emergency_sign_is_reported_but_not_triggered(self):
        data = self.post({"answers": answers(confusion="unsure")}).get_json()
        self.assertFalse(data["emergency"]["triggered"])
        self.assertEqual(data["emergency"]["unsure_signs"][0]["id"], "confusion")


class Helpers(unittest.TestCase):
    def test_build_facts_three_states(self):
        a = answers(fever="yes", cough="unsure")
        present, absent, unknown = app_module.build_facts(a)
        self.assertEqual(present, ["fever"])
        self.assertEqual(unknown, ["cough"])
        self.assertNotIn("fever", absent)
        self.assertNotIn("cough", absent)
        self.assertEqual(len(present) + len(absent) + len(unknown), len(SYMPTOM_IDS))


if __name__ == "__main__":
    unittest.main()
