"""Unit tests for engine/backward_chaining.py (and agreement with forward chaining)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.backward_chaining import (INCONCLUSIVE, SUPPORTED, UNSUPPORTED,
                                      backward_chain)
from engine.forward_chaining import forward_chain
from engine.knowledge_base import (DERIVED_FACTS, PATTERNS, RULES, SYMPTOMS,
                                   EMERGENCY_SIGNS)


def prove(goal, present=(), absent=(), unknown=(), rules=RULES):
    return backward_chain(goal, present, absent, unknown, rules)


class Statuses(unittest.TestCase):
    def test_supported(self):
        r = prove("pattern_cold_like", present=["runny_nose", "sneezing", "sore_throat"])
        self.assertEqual(r["status"], SUPPORTED)
        self.assertIn("sore_throat", r["facts_used"])

    def test_unsupported_when_all_rules_contradicted(self):
        r = prove("pattern_flu_like", absent=["fever", "chills"])
        self.assertEqual(r["status"], UNSUPPORTED)
        self.assertIn("fever", r["absent_conditions"])

    def test_unsupported_when_if_absent_condition_is_present(self):
        r = prove("pattern_allergy_like",
                  present=["itchy_eyes", "sneezing", "nasal_congestion", "fever"],
                  absent=["runny_nose"])
        self.assertEqual(r["status"], UNSUPPORTED)

    def test_inconclusive_when_unknown_blocks_only_path(self):
        r = prove("pattern_cold_like",
                  present=["runny_nose", "sneezing"], unknown=["sore_throat"],
                  absent=["cough", "nasal_congestion", "loss_of_smell"])
        self.assertEqual(r["status"], INCONCLUSIVE)
        self.assertIn("sore_throat", r["unknown_conditions"])

    def test_inconclusive_when_symptom_never_answered(self):
        r = prove("pattern_cold_like", present=["runny_nose", "sneezing"],
                  absent=["cough", "nasal_congestion", "loss_of_smell"])
        self.assertEqual(r["status"], INCONCLUSIVE)
        self.assertIn("sore_throat", r["unanswered_conditions"])

    def test_complete_rule_overrides_unknown_in_another_rule(self):
        # R7 is blocked by Not Sure (sore_throat) but R8 is complete.
        r = prove("pattern_cold_like",
                  present=["runny_nose", "sneezing", "cough"],
                  unknown=["sore_throat"], absent=["fever"])
        self.assertEqual(r["status"], SUPPORTED)
        status = {e["rule_id"]: e["status"] for e in r["rules_evaluated"]}
        self.assertEqual(status["R7"], INCONCLUSIVE)
        self.assertEqual(status["R8"], SUPPORTED)

    def test_unknown_if_absent_condition_is_inconclusive(self):
        r = prove("pattern_cold_like", present=["runny_nose", "sneezing", "cough"],
                  unknown=["fever"], absent=["sore_throat", "nasal_congestion"])
        self.assertEqual(r["status"], INCONCLUSIVE)

    def test_known_fact_goal_is_supported_immediately(self):
        r = prove("fever", present=["fever"])
        self.assertEqual(r["status"], SUPPORTED)
        self.assertEqual(r["rules_evaluated"], [])


class LoopProtection(unittest.TestCase):
    CYCLE = [
        {"id": "C1", "if": ["b"], "if_absent": [], "then": "a", "explanation": ""},
        {"id": "C2", "if": ["a"], "if_absent": [], "then": "b", "explanation": ""},
    ]

    def test_cyclic_rules_terminate(self):
        r = prove("a", rules=self.CYCLE)
        self.assertEqual(r["status"], UNSUPPORTED)
        self.assertIn("a", r["cycles_detected"])

    def test_cycle_does_not_block_alternative_rule(self):
        rules = self.CYCLE + [
            {"id": "C3", "if": ["x"], "if_absent": [], "then": "a", "explanation": ""}]
        r = prove("a", present=["x"], rules=rules)
        self.assertEqual(r["status"], SUPPORTED)

    def test_self_loop_terminates(self):
        rules = [{"id": "S", "if": ["a"], "if_absent": [], "then": "a", "explanation": ""}]
        r = prove("a", rules=rules)
        self.assertEqual(r["status"], UNSUPPORTED)

    def test_depth_limit_stops_deep_chain(self):
        rules = [{"id": f"D{i}", "if": [f"n{i + 1}"], "if_absent": [],
                  "then": f"n{i}", "explanation": ""} for i in range(40)]
        r = backward_chain("n0", ["n40"], [], [], rules, max_depth=10)
        self.assertEqual(r["status"], INCONCLUSIVE)


class TraceAndStructure(unittest.TestCase):
    def test_trace_has_depth_and_result(self):
        r = prove("pattern_flu_like", present=["fever", "chills", "cough", "fatigue"])
        self.assertTrue(r["trace"])
        self.assertEqual(r["trace"][0]["depth"], 0)
        self.assertEqual(r["trace"][-1]["kind"], "result")
        self.assertTrue(r["rules_evaluated"])

    def test_works_backward_from_goal(self):
        r = prove("pattern_cold_like", present=["runny_nose", "sneezing", "sore_throat"])
        self.assertEqual(r["trace"][0]["kind"], "goal")  # starts at the hypothesis


class KnowledgeBaseSanity(unittest.TestCase):
    def test_rules_reference_known_ids_only(self):
        base = {s["id"] for s in SYMPTOMS}
        known = base | set(DERIVED_FACTS) | set(PATTERNS)
        for rule in RULES:
            self.assertIn(rule["then"], set(DERIVED_FACTS) | set(PATTERNS))
            for c in rule["if"]:
                self.assertIn(c, known, rule["id"])
            for c in rule["if_absent"]:
                self.assertIn(c, base, f"{rule['id']}: if_absent must use base symptoms")

    def test_rule_ids_unique_and_no_emergency_signs_in_rules(self):
        ids = [r["id"] for r in RULES]
        self.assertEqual(len(ids), len(set(ids)))
        emergency = {e["id"] for e in EMERGENCY_SIGNS}
        for rule in RULES:
            self.assertFalse(emergency & (set(rule["if"]) | set(rule["if_absent"]) | {rule["then"]}))


class AlgorithmAgreement(unittest.TestCase):
    """Both algorithms read the same rules, so for the real knowledge base
    forward 'derived pattern' must equal backward 'supported'."""

    def test_agreement_on_random_answer_sets(self):
        rng = random.Random(2024)
        ids = [s["id"] for s in SYMPTOMS]
        for _ in range(400):
            states = {i: rng.choice(["yes", "no", "unsure", "skip"]) for i in ids}
            present = [i for i, v in states.items() if v == "yes"]
            absent = [i for i, v in states.items() if v == "no"]
            unknown = [i for i, v in states.items() if v == "unsure"]

            fwd = forward_chain(present, absent, unknown, RULES, pattern_ids=list(PATTERNS))
            for pid in PATTERNS:
                bwd = backward_chain(pid, present, absent, unknown, RULES)
                self.assertEqual(pid in fwd["patterns"], bwd["status"] == SUPPORTED,
                                 f"disagreement on {pid} for {states}")

    def test_unsupported_never_when_unknown_is_only_blocker(self):
        # A pattern forward chaining could not derive must be unsupported OR inconclusive.
        present = ["fever", "cough"]
        r = prove("pattern_flu_like", present=present, unknown=["fatigue", "headache",
                                                                "body_aches", "chills"])
        self.assertEqual(r["status"], INCONCLUSIVE)


if __name__ == "__main__":
    unittest.main()
