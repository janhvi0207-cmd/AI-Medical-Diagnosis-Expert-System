"""
Flask backend for the AI Medical Diagnosis System (EDUCATIONAL USE ONLY).

Responsibilities of this file (and nothing else):
  1. serve the three HTML pages,
  2. expose the question list,
  3. validate a submitted assessment,
  4. turn answers into facts (present / absent / unknown),
  5. check emergency warning signs INDEPENDENTLY of the rules,
  6. call the forward- and backward-chaining engines on the SAME facts,
  7. return one structured JSON response.

Nothing is written to disk or a database and nothing is sent to any external
service: answers exist only in memory while a request is processed.

Run:  python app.py      then open http://127.0.0.1:5000
"""
from flask import Flask, jsonify, render_template, request

from engine.backward_chaining import SUPPORTED, backward_chain
from engine.forward_chaining import forward_chain
from engine.knowledge_base import (EMERGENCY_MESSAGE, EMERGENCY_SIGNS, PATTERNS,
                                   RULES, SYMPTOMS, get_labels)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # answers are tiny; reject big bodies

VALID_ANSWERS = {"yes", "no", "unsure"}
SYMPTOM_IDS = [s["id"] for s in SYMPTOMS]
EMERGENCY_IDS = [e["id"] for e in EMERGENCY_SIGNS]
ALL_QUESTION_IDS = EMERGENCY_IDS + SYMPTOM_IDS
LABELS = get_labels()

DISCLAIMER = (
    "This tool is an educational demonstration of rule-based AI. It is not a "
    "medical device and cannot diagnose, confirm or rule out any condition. "
    "Its rules are illustrative examples and have not been medically validated."
)

SAFETY_ADVICE = [
    "Talk to a qualified doctor or pharmacist about any symptom that worries you, "
    "gets worse, or lasts longer than you expect.",
    "Seek urgent medical help for trouble breathing, chest pain, confusion, "
    "bluish lips or face, or any symptom that feels severe or sudden.",
    "Children, older adults, pregnant people and anyone with a long-term health "
    "condition should seek professional advice early.",
    "This tool does not recommend medicines or doses.",
    "Your answers are processed in memory only; they are not stored or sent to "
    "any external service.",
]


# ---------------------------------------------------------------------------
# Validation and fact building
# ---------------------------------------------------------------------------
def validate_payload(payload):
    """Return (answers, errors). `errors` is a list of readable messages."""
    if not isinstance(payload, dict):
        return None, ["Request body must be a JSON object."]
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        return None, ['Request must contain an "answers" object.']

    errors = []
    unknown_keys = [k for k in answers if k not in ALL_QUESTION_IDS]
    if unknown_keys:
        errors.append("Unknown question id(s): " + ", ".join(sorted(map(str, unknown_keys))))

    missing = [q for q in ALL_QUESTION_IDS if q not in answers]
    if missing:
        errors.append("Unanswered question(s): " + ", ".join(missing))

    invalid = [k for k, v in answers.items()
               if k in ALL_QUESTION_IDS and v not in VALID_ANSWERS]
    if invalid:
        errors.append('Answers must be "yes", "no" or "unsure". Invalid for: '
                      + ", ".join(invalid))
    if errors:
        return None, errors
    return answers, []


def build_facts(answers):
    """
    Convert validated answers to the three knowledge states.
    Only SYMPTOMS become facts for the rule engines; emergency signs are kept out.
    """
    present = [s for s in SYMPTOM_IDS if answers[s] == "yes"]
    absent = [s for s in SYMPTOM_IDS if answers[s] == "no"]
    unknown = [s for s in SYMPTOM_IDS if answers[s] == "unsure"]
    return present, absent, unknown


def check_emergency(answers):
    """Emergency check: separate from, and not changed by, the rule results."""
    signs = [{"id": e["id"], "label": e["label"]}
             for e in EMERGENCY_SIGNS if answers[e["id"]] == "yes"]
    unsure = [{"id": e["id"], "label": e["label"]}
              for e in EMERGENCY_SIGNS if answers[e["id"]] == "unsure"]
    return {"triggered": bool(signs), "signs": signs, "unsure_signs": unsure,
            "message": EMERGENCY_MESSAGE}


# ---------------------------------------------------------------------------
# Helpers that explain results
# ---------------------------------------------------------------------------
def supporting_chain(pattern_id, fired_rules):
    """
    Walk back through the rules that fired for a pattern and collect the base
    symptoms and rule ids that justify it (used only for explanation).
    """
    base = set(SYMPTOM_IDS)
    by_conclusion = {}
    for fr in fired_rules:
        by_conclusion.setdefault(fr["conclusion"], []).append(fr)
    symptoms, rule_ids, seen = [], [], set()

    def walk(fact):
        if fact in seen:
            return
        seen.add(fact)
        for fr in by_conclusion.get(fact, []):
            if fr["rule_id"] not in rule_ids:
                rule_ids.append(fr["rule_id"])
            for cond in fr["because"]:
                if cond.startswith("not "):
                    continue
                if cond in base:
                    if cond not in symptoms:
                        symptoms.append(cond)
                else:
                    walk(cond)

    walk(pattern_id)
    return symptoms, rule_ids


def requirement_text(fact):
    """Plain-language 'how could this derived fact be established' (from the rules)."""
    options = [" + ".join(LABELS.get(c, c) for c in r["if"])
               for r in RULES if r["then"] == fact]
    return " or ".join(options)


def closest_rule(pattern_id, rule_report):
    """
    For a pattern that was NOT supported, pick the rule that came nearest
    (fewest failed conditions, then most met) so the user can see what was
    missing. This is a plain list of conditions, not a score.
    """
    candidates = [r for r in rule_report if r["conclusion"] == pattern_id]
    if not candidates:
        return None

    def progress(r):
        states = [c["state"] for c in r["conditions"]]
        return (-states.count("failed"), states.count("met"))

    best = max(candidates, key=progress)
    conditions = []
    for c in best["conditions"]:
        item = dict(c)
        if c["state"] == "not_established" and c["fact"] not in SYMPTOM_IDS:
            item["how"] = requirement_text(c["fact"])
        conditions.append(item)
    return {"rule_id": best["rule_id"], "explanation": best["explanation"],
            "conditions": conditions}


def named(ids):
    return [{"id": i, "label": LABELS.get(i, i)} for i in ids]


def run_assessment(answers):
    """Run both engines on the same facts and assemble the JSON response."""
    present, absent, unknown = build_facts(answers)
    emergency = check_emergency(answers)
    pattern_ids = list(PATTERNS)

    forward = forward_chain(present, absent, unknown, RULES,
                            pattern_ids=pattern_ids, labels=LABELS)
    backward = [backward_chain(pid, present, absent, unknown, RULES, labels=LABELS)
                for pid in pattern_ids]
    backward_by_goal = {b["goal"]: b for b in backward}

    patterns = []
    for pid in pattern_ids:
        info = PATTERNS[pid]
        supported_fwd = pid in forward["patterns"]
        bwd = backward_by_goal[pid]
        entry = {
            "id": pid, "label": info["label"], "description": info["description"],
            "forward_supported": supported_fwd,
            "backward_status": bwd["status"],
            "backward_status_label": bwd["status_label"],
        }
        if supported_fwd:
            symptoms, rule_ids = supporting_chain(pid, forward["fired_rules"])
            entry["supporting_symptoms"] = named(symptoms)
            entry["rules_used"] = rule_ids
        else:
            entry["closest_rule"] = closest_rule(pid, forward["rule_report"])
        patterns.append(entry)

    supported = [p for p in patterns if p["forward_supported"]]
    inconclusive = [p for p in patterns if p["backward_status"] == "inconclusive"
                    and not p["forward_supported"]]

    if supported:
        headline = (f"{len(supported)} example symptom pattern(s) matched your answers")
        detail = ("These are educational possibilities from illustrative rules, "
                  "not diagnoses.")
    elif inconclusive:
        headline = "No pattern was fully matched, but some could not be ruled out"
        detail = ("Some answers were Not Sure, so the system cannot conclude "
                  "either way for: " + ", ".join(p["label"] for p in inconclusive) + ".")
    else:
        headline = "No supported symptom pattern was found"
        detail = ("Your answers did not satisfy any of the example rules. This does "
                  "not mean nothing is wrong; see a professional if you are concerned.")

    if emergency["triggered"]:
        headline = "Urgent warning signs were reported"
        detail = ("Seek emergency care now. The pattern results below are secondary "
                  "and cannot override this guidance.")

    fired_count = len(forward["fired_rules"])
    comparison = {
        "points": [
            {"aspect": "Starting point",
             "forward": "Starts from all the known facts (your Yes answers).",
             "backward": "Starts from one hypothesis (a pattern) and asks what would prove it."},
            {"aspect": "Direction",
             "forward": "Data-driven: facts -> rules -> new facts -> patterns.",
             "backward": "Goal-driven: pattern -> rules -> conditions -> sub-goals."},
            {"aspect": "What it explores",
             "forward": "Every rule that can fire, whether or not it matters for a goal.",
             "backward": "Only the rules relevant to the goal being tested."},
            {"aspect": "Result style",
             "forward": "Lists what it could derive; unfired rules are explained afterwards.",
             "backward": "Gives supported / unsupported / inconclusive for each hypothesis."},
            {"aspect": "Not Sure answers",
             "forward": "A rule needing a Not Sure fact simply does not fire.",
             "backward": "The goal becomes inconclusive, unless another complete rule supports it."},
        ],
        "this_run": (
            f"Forward chaining made {len(forward['derived_facts'])} new inference(s) by firing "
            f"{fired_count} rule(s) in {forward['iterations']} pass(es). Backward chaining tested "
            f"{len(backward)} hypotheses and made "
            f"{sum(len(b['rules_evaluated']) for b in backward)} rule check(s) in total "
            f"(a rule is re-checked whenever a sub-goal needs it)."),
        "agree": all((p["backward_status"] == SUPPORTED) == p["forward_supported"]
                     for p in patterns),
    }

    return {
        "emergency": emergency,
        "summary": {
            "headline": headline, "detail": detail,
            "counts": {"yes": len(present), "no": len(absent), "unsure": len(unknown)},
            "supported_patterns": len(supported),
        },
        "answers": {"present": named(present), "absent": named(absent),
                    "unknown": named(unknown)},
        "patterns": patterns,
        "forward": forward,
        "backward": backward,
        "comparison": comparison,
        "labels": LABELS,
        "disclaimer": DISCLAIMER,
        "safety": SAFETY_ADVICE,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/assessment")
def assessment():
    return render_template("assessment.html")


@app.route("/results")
def results():
    return render_template("results.html")


@app.route("/api/questions")
def api_questions():
    return jsonify({
        "emergency_signs": EMERGENCY_SIGNS,
        "symptoms": SYMPTOMS,
        "emergency_message": EMERGENCY_MESSAGE,
        "disclaimer": DISCLAIMER,
    })


@app.route("/api/assess", methods=["POST"])
def api_assess():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be valid JSON.",
                        "details": []}), 400
    answers, errors = validate_payload(payload)
    if errors:
        return jsonify({"error": "Invalid assessment request.", "details": errors}), 400
    return jsonify(run_assessment(answers))


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Request too large.", "details": []}), 413


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found.", "details": []}), 404
    return render_template("index.html"), 404


@app.errorhandler(405)
def bad_method(_):
    return jsonify({"error": "Method not allowed.", "details": []}), 405


if __name__ == "__main__":
    # debug=False: the debugger must not be exposed; fine for a local lab demo.
    app.run(host="127.0.0.1", port=5000, debug=False)
