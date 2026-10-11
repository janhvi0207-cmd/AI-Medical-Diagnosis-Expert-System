"""
Knowledge base for the AI Medical Diagnosis System (EDUCATIONAL USE ONLY).

This module holds DATA only: symptoms, emergency warning signs, and the
if-then rules. It contains no reasoning algorithm. The forward- and
backward-chaining engines receive these rules as input.

IMPORTANT
---------
* The rules below are small, illustrative examples written to demonstrate
  rule-based reasoning in a college AI laboratory.
* They are NOT medically validated and must never be used to diagnose,
  confirm, or rule out any condition.
* "Patterns" are only combinations of answers that match an example rule.

Rule format
-----------
Each rule is a dictionary:

    {
        "id":        unique rule name, e.g. "R1"
        "if":        list of facts that must be PRESENT (answered Yes or
                     already inferred by another rule)
        "if_absent": list of symptoms that must be explicitly ABSENT
                     (answered No). "Not Sure" does NOT satisfy this.
        "then":      the single fact this rule concludes
        "explanation": plain-language reason, shown in the reasoning trace
    }

Three states of a symptom
-------------------------
    Yes      -> symptom is a known PRESENT fact
    No       -> symptom is explicitly ABSENT
    Not Sure -> symptom is UNKNOWN (never treated as support)

Note: "if_absent" must only reference base symptoms (things the user is
asked about). Tests enforce this so both algorithms agree.
"""

# --------------------------------------------------------------------------
# Base symptoms (asked in the questionnaire). These are the observable facts.
# --------------------------------------------------------------------------
SYMPTOMS = [
    {"id": "fever", "label": "Fever",
     "question": "Have you had a fever (feeling very hot, or a measured temperature above normal)?",
     "hint": "Answer Yes if you have felt feverish or measured a high temperature."},
    {"id": "chills", "label": "Chills",
     "question": "Have you had chills or shivering?",
     "hint": "Feeling cold and shaky, often with a fever."},
    {"id": "cough", "label": "Cough",
     "question": "Do you have a cough?",
     "hint": "Dry or with phlegm."},
    {"id": "sore_throat", "label": "Sore throat",
     "question": "Do you have a sore or scratchy throat?",
     "hint": "Pain or irritation when swallowing or talking."},
    {"id": "runny_nose", "label": "Runny nose",
     "question": "Do you have a runny nose?",
     "hint": "Clear or coloured discharge from the nose."},
    {"id": "nasal_congestion", "label": "Blocked nose",
     "question": "Does your nose feel blocked or congested?",
     "hint": "Difficulty breathing through the nose."},
    {"id": "sneezing", "label": "Sneezing",
     "question": "Have you been sneezing a lot?",
     "hint": "Frequent or repeated sneezing."},
    {"id": "body_aches", "label": "Body aches",
     "question": "Do you have general body or muscle aches?",
     "hint": "Aching muscles or joints."},
    {"id": "fatigue", "label": "Unusual tiredness",
     "question": "Do you feel unusually tired or exhausted?",
     "hint": "More tired than your normal day-to-day tiredness."},
    {"id": "headache", "label": "Headache",
     "question": "Do you have a headache?",
     "hint": "Any ongoing head pain."},
    {"id": "itchy_eyes", "label": "Itchy or watery eyes",
     "question": "Are your eyes itchy or watery?",
     "hint": "Itching, redness or watering of the eyes."},
    {"id": "loss_of_smell", "label": "Reduced sense of smell",
     "question": "Has your sense of smell been reduced or lost?",
     "hint": "Things smell weaker than usual or not at all."},
]

# --------------------------------------------------------------------------
# Emergency warning signs. These are handled SEPARATELY from the rules:
# they are never passed to the chaining engines and rule results can never
# override the urgent guidance they trigger.
# --------------------------------------------------------------------------
EMERGENCY_SIGNS = [
    {"id": "difficulty_breathing", "label": "Difficulty breathing",
     "question": "Are you having severe difficulty breathing or are you struggling for breath?",
     "hint": "Cannot speak full sentences, or breathing feels very hard."},
    {"id": "chest_pain", "label": "Chest pain or pressure",
     "question": "Do you have chest pain, tightness, or pressure that is severe or does not go away?",
     "hint": "Especially if it spreads to the arm, jaw or back."},
    {"id": "confusion", "label": "Confusion or hard to wake",
     "question": "Are you (or the person being assessed) newly confused, very drowsy, or hard to wake?",
     "hint": "Not thinking clearly, or unusually difficult to keep awake."},
    {"id": "bluish_lips", "label": "Bluish lips or face",
     "question": "Are the lips, face or fingertips turning blue or very pale or grey?",
     "hint": "A change in colour that is new."},
]

EMERGENCY_MESSAGE = (
    "One or more urgent warning signs were selected. Please seek emergency "
    "medical care or call your local emergency number NOW. Do not wait for "
    "this educational tool, and do not rely on its results."
)

# --------------------------------------------------------------------------
# Intermediate (derived) facts: they are concluded by rules and are not asked
# directly. They make chaining multi-step instead of one flat lookup.
# --------------------------------------------------------------------------
DERIVED_FACTS = {
    "sign_nasal": "Nasal symptoms present",
    "sign_systemic": "Whole-body symptoms present",
    "sign_allergic_eye_nose": "Eye-and-nose irritation present",
}

# --------------------------------------------------------------------------
# Symptom patterns (the possible "goals"). These are NOT diseases.
# --------------------------------------------------------------------------
PATTERNS = {
    "pattern_cold_like": {
        "label": "Cold-like symptom pattern",
        "description": "Mainly nose and throat symptoms, usually without whole-body symptoms.",
    },
    "pattern_flu_like": {
        "label": "Flu-like symptom pattern",
        "description": "Whole-body symptoms such as fever, aches and tiredness, together with respiratory symptoms.",
    },
    "pattern_allergy_like": {
        "label": "Allergy-like symptom pattern",
        "description": "Sneezing and itchy eyes or nose, typically without fever.",
    },
}

# --------------------------------------------------------------------------
# Rules (ILLUSTRATIVE ONLY - not clinically validated).
#
# They were written to be easy to follow in a lab demonstration, and are
# deliberately simple: most need only two or three conditions. Several rules
# share a conclusion; any ONE complete rule is enough (logical OR).
# "if_absent" conditions need an explicit No, so Not Sure never satisfies them.
# --------------------------------------------------------------------------
def _rule(rid, conditions, then, explanation, absent=()):
    return {"id": rid, "if": list(conditions), "if_absent": list(absent),
            "then": then, "explanation": explanation}


RULES = [
    # --- Step 1: combine raw symptoms into intermediate facts -------------
    _rule("R1", ["runny_nose", "sneezing"], "sign_nasal",
          "Runny nose together with sneezing counts as nasal symptoms."),
    _rule("R2", ["runny_nose", "nasal_congestion"], "sign_nasal",
          "Runny nose together with a blocked nose counts as nasal symptoms."),
    _rule("R3", ["sneezing", "nasal_congestion"], "sign_nasal",
          "Sneezing together with a blocked nose counts as nasal symptoms."),
    _rule("R4", ["fever", "body_aches"], "sign_systemic",
          "Fever together with body aches counts as whole-body symptoms."),
    _rule("R5", ["fever", "chills"], "sign_systemic",
          "Fever together with chills counts as whole-body symptoms."),
    _rule("R6", ["itchy_eyes", "sneezing"], "sign_allergic_eye_nose",
          "Itchy eyes together with sneezing counts as eye-and-nose irritation."),

    # --- Step 2a: example cold-like pattern -------------------------------
    _rule("R7", ["sign_nasal", "sore_throat"], "pattern_cold_like",
          "Nasal symptoms plus a sore throat match the example cold-like pattern."),
    _rule("R8", ["sign_nasal", "cough"], "pattern_cold_like",
          "Nasal symptoms plus cough, with no fever, match the example cold-like pattern.",
          absent=["fever"]),
    _rule("R9", ["runny_nose", "sore_throat"], "pattern_cold_like",
          "Runny nose plus a sore throat match the example cold-like pattern."),
    _rule("R10", ["sore_throat", "cough"], "pattern_cold_like",
          "Sore throat plus cough, with no fever, match the example cold-like pattern.",
          absent=["fever"]),
    _rule("R11", ["nasal_congestion", "loss_of_smell"], "pattern_cold_like",
          "A blocked nose with reduced smell, with no fever, matches the example cold-like pattern.",
          absent=["fever"]),

    # --- Step 2b: example flu-like pattern --------------------------------
    _rule("R12", ["sign_systemic", "cough"], "pattern_flu_like",
          "Whole-body symptoms plus cough match the example flu-like pattern."),
    _rule("R13", ["sign_systemic", "fatigue"], "pattern_flu_like",
          "Whole-body symptoms plus unusual tiredness match the example flu-like pattern."),
    _rule("R14", ["sign_systemic", "headache"], "pattern_flu_like",
          "Whole-body symptoms plus headache match the example flu-like pattern."),
    _rule("R15", ["fever", "cough", "fatigue"], "pattern_flu_like",
          "Fever, cough and unusual tiredness together match the example flu-like pattern."),
    _rule("R16", ["fever", "cough"], "pattern_flu_like",
          "Fever with cough, without sneezing or itchy eyes, matches the example flu-like pattern.",
          absent=["sneezing", "itchy_eyes"]),

    # --- Step 2c: example allergy-like pattern ----------------------------
    _rule("R17", ["sign_allergic_eye_nose"], "pattern_allergy_like",
          "Eye-and-nose irritation with no fever matches the example allergy-like pattern.",
          absent=["fever"]),
    _rule("R18", ["itchy_eyes", "runny_nose"], "pattern_allergy_like",
          "Itchy eyes plus a runny nose, with no fever, match the example allergy-like pattern.",
          absent=["fever"]),
    _rule("R19", ["sign_nasal"], "pattern_allergy_like",
          "Nasal symptoms with no fever and no sore throat match the example allergy-like pattern.",
          absent=["fever", "sore_throat"]),
]


def get_labels():
    """Return {id: human-readable label} for every symptom, sign, derived fact and pattern."""
    labels = {}
    for item in SYMPTOMS + EMERGENCY_SIGNS:
        labels[item["id"]] = item["label"]
    labels.update(DERIVED_FACTS)
    for pid, info in PATTERNS.items():
        labels[pid] = info["label"]
    return labels
