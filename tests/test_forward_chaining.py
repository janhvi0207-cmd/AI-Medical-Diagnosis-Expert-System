"""Unit tests for engine/forward_chaining.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.forward_chaining import forward_chain
from engine.knowledge_base import PATTERNS, RULES

PATTERN_IDS = list(PATTERNS)


def run(present=(), absent=(), unknown=(), rules=RULES, **kw):
    return forward_chain(present, absent, unknown, rules,
                         pattern_ids=kw.pop("pattern_ids", PATTERN_IDS), **kw)


class RuleMatching(unittest.TestCase):
    def test_single_rule_fires_when_conditions_met(self):
        r = run(present=["runny_nose", "sneezing"])
        self.assertIn("sign_nasal", r["final_facts"])
        self.assertIn("R1", [f["rule_id"] for f in r["fired_rules"]])

    def test_rule_does_not_fire_when_condition_missing(self):
        r = run(present=["runny_nose"])
        self.assertNotIn("sign_nasal", r["final_facts"])
        self.assertEqual(r["fired_rules"], [])

    def test_chain_of_rules_reaches_pattern(self):
        # R1 -> sign_nasal, then R7 -> pattern_cold_like (one rule feeds the next)
        r = run(present=["runny_nose", "sneezing", "sore_throat"])
        self.assertEqual(r["patterns"], ["pattern_cold_like"])
        fired = [f["rule_id"] for f in r["fired_rules"]]
        self.assertLess(fired.index("R1"), fired.index("R7"))

    def test_flu_like_pattern(self):
        r = run(present=["fever", "body_aches", "cough", "fatigue"])
        self.assertIn("pattern_flu_like", r["patterns"])

    def test_no_patterns_when_nothing_matches(self):
        r = run(present=["headache"])
        self.assertEqual(r["patterns"], [])

    def test_multiple_patterns_can_match(self):
        r = run(present=["runny_nose", "sneezing", "sore_throat", "itchy_eyes",
                         "nasal_congestion"], absent=["fever", "body_aches"])
        self.assertIn("pattern_cold_like", r["patterns"])
        self.assertIn("pattern_allergy_like", r["patterns"])


class AbsentAndUnknown(unittest.TestCase):
    def test_unknown_symptom_does_not_support_rule(self):
        r = run(present=["runny_nose"], unknown=["sneezing"], absent=["nasal_congestion"])
        self.assertNotIn("sign_nasal", r["final_facts"])
        blocked = {n["rule_id"]: n for n in r["not_fired_rules"]}
        self.assertEqual(blocked["R1"]["status"], "unknown")

    def test_absent_symptom_blocks_rule(self):
        r = run(present=["runny_nose"], absent=["sneezing", "nasal_congestion"])
        blocked = {n["rule_id"]: n for n in r["not_fired_rules"]}
        self.assertEqual(blocked["R1"]["status"], "contradicted")

    def test_if_absent_requires_explicit_no(self):
        base = ["sign_allergic_eye_nose", "nasal_congestion"]
        # fever answered No -> R10 fires
        self.assertIn("pattern_allergy_like", run(present=base, absent=["fever"])["patterns"])
        # fever Not Sure -> R10 must NOT fire
        self.assertNotIn("pattern_allergy_like", run(present=base, unknown=["fever"])["patterns"])
        # fever never answered -> R10 must NOT fire
        self.assertNotIn("pattern_allergy_like", run(present=base)["patterns"])
        # fever present -> R10 must NOT fire
        self.assertNotIn("pattern_allergy_like", run(present=base + ["fever"])["patterns"])


class DuplicatesAndTermination(unittest.TestCase):
    def test_duplicate_facts_not_added(self):
        # R1, R2 and R3 all conclude sign_nasal.
        r = run(present=["runny_nose", "sneezing", "nasal_congestion"])
        self.assertEqual(r["final_facts"].count("sign_nasal"), 1)
        self.assertEqual(len(r["final_facts"]), len(set(r["final_facts"])))
        new_flags = [f["new_fact"] for f in r["fired_rules"] if f["conclusion"] == "sign_nasal"]
        self.assertEqual(len(new_flags), 3)          # all three rules fired...
        self.assertEqual(new_flags.count(True), 1)   # ...but only one added the fact

    def test_each_rule_fires_at_most_once(self):
        r = run(present=["runny_nose", "sneezing", "nasal_congestion", "sore_throat"])
        ids = [f["rule_id"] for f in r["fired_rules"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_cyclic_rules_terminate(self):
        rules = [
            {"id": "C1", "if": ["a"], "if_absent": [], "then": "b", "explanation": "a->b"},
            {"id": "C2", "if": ["b"], "if_absent": [], "then": "a", "explanation": "b->a"},
        ]
        r = forward_chain(["a"], [], [], rules, pattern_ids=["b"])
        self.assertEqual(r["final_facts"], ["a", "b"])
        self.assertFalse(r["hit_iteration_limit"])

    def test_self_referencing_rule_terminates(self):
        rules = [{"id": "S", "if": ["a"], "if_absent": [], "then": "a", "explanation": "loop"}]
        r = forward_chain(["a"], [], [], rules)
        self.assertEqual(r["final_facts"], ["a"])

    def test_iteration_limit_is_reported(self):
        # Rules listed in reverse order: each pass can only advance one link.
        rules = [
            {"id": "L3", "if": ["c"], "if_absent": [], "then": "d", "explanation": ""},
            {"id": "L2", "if": ["b"], "if_absent": [], "then": "c", "explanation": ""},
            {"id": "L1", "if": ["a"], "if_absent": [], "then": "b", "explanation": ""},
        ]
        r = forward_chain(["a"], [], [], rules, max_iterations=2)
        self.assertTrue(r["hit_iteration_limit"])
        self.assertNotIn("d", r["final_facts"])
        full = forward_chain(["a"], [], [], rules, max_iterations=10)
        self.assertIn("d", full["final_facts"])
        self.assertFalse(full["hit_iteration_limit"])


class RealisticAnswerSets(unittest.TestCase):
    """Everyday combinations (everything not listed is answered No) must give
    a pattern. This guards against the rules becoming too strict again."""

    CASES = [
        (["runny_nose", "sore_throat"], "pattern_cold_like"),
        (["sore_throat", "cough", "nasal_congestion"], "pattern_cold_like"),
        (["runny_nose", "sneezing", "cough"], "pattern_cold_like"),
        (["fever", "cough", "fatigue"], "pattern_flu_like"),
        (["fever", "body_aches", "headache"], "pattern_flu_like"),
        (["fever", "chills", "fatigue"], "pattern_flu_like"),
        (["fever", "sore_throat", "cough"], "pattern_flu_like"),
        (["sneezing", "itchy_eyes"], "pattern_allergy_like"),
        (["itchy_eyes", "runny_nose"], "pattern_allergy_like"),
        (["runny_nose", "sneezing"], "pattern_allergy_like"),
    ]

    def test_each_case_supports_expected_pattern(self):
        from engine.knowledge_base import SYMPTOMS
        ids = [s["id"] for s in SYMPTOMS]
        for yes, expected in self.CASES:
            absent = [i for i in ids if i not in yes]
            r = forward_chain(yes, absent, [], RULES, pattern_ids=PATTERN_IDS)
            self.assertIn(expected, r["patterns"], f"{yes} should support {expected}")

    def test_single_symptom_is_not_enough(self):
        from engine.knowledge_base import SYMPTOMS
        ids = [s["id"] for s in SYMPTOMS]
        for sym in ids:
            r = forward_chain([sym], [i for i in ids if i != sym], [], RULES,
                              pattern_ids=PATTERN_IDS)
            self.assertEqual(r["patterns"], [], f"{sym} alone should not support a pattern")


class RuleReport(unittest.TestCase):
    def report(self, **kw):
        return {x["rule_id"]: x for x in run(**kw)["rule_report"]}

    def test_every_rule_is_reported(self):
        self.assertEqual(len(run()["rule_report"]), len(RULES))

    def test_condition_states(self):
        rep = self.report(present=["runny_nose"], absent=["sneezing"],
                          unknown=["nasal_congestion"])
        states = {c["fact"]: c["state"] for c in rep["R1"]["conditions"]}
        self.assertEqual(states, {"runny_nose": "met", "sneezing": "failed"})
        states = {c["fact"]: c["state"] for c in rep["R2"]["conditions"]}
        self.assertEqual(states["nasal_congestion"], "unknown")
        states = {c["fact"]: c["state"] for c in rep["R9"]["conditions"]}
        self.assertEqual(states["sore_throat"], "not_established")  # never answered

    def test_must_be_absent_states(self):
        base = ["sneezing", "itchy_eyes"]
        for kwargs, expected in [({"absent": ["fever"]}, "met"),
                                 ({"present": ["fever"]}, "failed"),
                                 ({"unknown": ["fever"]}, "unknown"),
                                 ({}, "not_established")]:
            kw = dict(kwargs)
            kw["present"] = base + kw.get("present", [])
            fever = [c for c in self.report(**kw)["R17"]["conditions"]
                     if c["fact"] == "fever"][0]
            self.assertEqual(fever["state"], expected, kwargs)
            self.assertEqual(fever["need"], "absent")

    def test_fired_flag_matches_fired_rules(self):
        r = run(present=["runny_nose", "sneezing", "sore_throat"])
        fired_ids = {f["rule_id"] for f in r["fired_rules"]}
        for entry in r["rule_report"]:
            self.assertEqual(entry["fired"], entry["rule_id"] in fired_ids)


class Trace(unittest.TestCase):
    def test_trace_is_ordered_and_explained(self):
        r = run(present=["runny_nose", "sneezing", "sore_throat"],
                labels={"sign_nasal": "Nasal symptoms present"})
        steps = [t["step"] for t in r["trace"]]
        self.assertEqual(steps, sorted(steps))
        self.assertEqual(r["trace"][0]["kind"], "start")
        self.assertEqual(r["trace"][-1]["kind"], "stop")
        self.assertTrue(any("Nasal symptoms present" in t["text"] for t in r["trace"]))


if __name__ == "__main__":
    unittest.main()
