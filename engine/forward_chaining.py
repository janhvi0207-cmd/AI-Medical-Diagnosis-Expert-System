"""
Forward chaining (DATA-DRIVEN reasoning).

Idea: start from what we KNOW (facts from the answers), repeatedly look for
rules whose conditions are all satisfied, fire them to add new facts, and
stop when nothing new can be inferred.

    known facts --> fire rules --> new facts --> fire more rules --> ... --> stop

This module is independent of Flask and of the knowledge base: the rules and
facts are passed in as arguments, which also makes it easy to unit-test.

Three states are kept separate:
    present  - symptom answered Yes (or fact inferred)
    absent   - symptom answered No
    unknown  - symptom answered Not Sure (never counts as support)
"""


def _check_rule(rule, facts, absent, unknown):
    """
    Compare one rule with the current knowledge.

    Returns a dict with a `status`:
        "met"           every condition satisfied -> rule may fire
        "contradicted"  a required symptom is absent, or a symptom that must
                        be absent is present -> rule cannot fire
        "unknown"       no contradiction, but a condition is Not Sure
        "missing"       no contradiction, but a condition is neither known
                        nor answered (e.g. an intermediate fact not derived)
    plus the lists of conditions behind that status.
    """
    contradicted, unknown_conditions, missing = [], [], []

    for cond in rule["if"]:            # must be PRESENT
        if cond in facts:
            continue
        if cond in absent:
            contradicted.append(cond)
        elif cond in unknown:
            unknown_conditions.append(cond)
        else:
            missing.append(cond)

    for cond in rule.get("if_absent", []):   # must be explicitly ABSENT
        if cond in absent:
            continue
        if cond in facts:
            contradicted.append(cond)
        elif cond in unknown:
            unknown_conditions.append(cond)
        else:
            missing.append(cond)

    if contradicted:
        status = "contradicted"
    elif unknown_conditions:
        status = "unknown"
    elif missing:
        status = "missing"
    else:
        status = "met"
    return {"status": status, "contradicted": contradicted,
            "unknown": unknown_conditions, "missing": missing}


def forward_chain(present, absent, unknown, rules, pattern_ids=(),
                  labels=None, max_iterations=50):
    """
    Run forward chaining.

    present, absent, unknown : iterables of fact ids (the three answer states)
    rules                    : list of rule dicts (see knowledge_base.py)
    pattern_ids              : fact ids that count as "possible patterns"
    labels                   : optional {id: readable name} used in the trace
    max_iterations           : safety cap on passes over the rule list

    Returns a dict containing the final facts, fired rules, rules that could
    not fire (with reasons), the patterns derived, and a step-by-step trace.
    """
    labels = labels or {}
    name = lambda fid: labels.get(fid, fid)          # noqa: E731
    names = lambda ids: ", ".join(name(i) for i in ids)  # noqa: E731

    facts = set(present)          # a set => duplicates are impossible
    absent = set(absent)
    unknown = set(unknown)
    initial_facts = sorted(facts)

    fired_ids = set()             # each rule fires at most once
    fired_rules = []
    trace = []
    step = 0

    def log(kind, text):
        nonlocal step
        step += 1
        trace.append({"step": step, "kind": kind, "text": text})

    log("start", f"Start with {len(facts)} known fact(s): "
                 f"{names(sorted(facts)) or 'none'}.")
    if absent:
        log("info", f"Explicitly absent (answered No): {names(sorted(absent))}.")
    if unknown:
        log("info", f"Unknown (answered Not Sure, never used as support): "
                    f"{names(sorted(unknown))}.")

    hit_limit = False
    iterations = 0
    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        log("iteration", f"Pass {iteration}: scan every rule that has not fired yet.")
        progressed = False

        for rule in rules:
            if rule["id"] in fired_ids:
                continue
            check = _check_rule(rule, facts, absent, unknown)
            if check["status"] != "met":
                continue

            fired_ids.add(rule["id"])
            conclusion = rule["then"]
            because = list(rule["if"]) + [f"not {c}" for c in rule.get("if_absent", [])]
            is_new = conclusion not in facts
            if is_new:
                facts.add(conclusion)
                progressed = True
                log("fire", f"Rule {rule['id']} FIRED: {rule['explanation']} "
                            f"New fact added: {name(conclusion)}.")
            else:
                log("redundant", f"Rule {rule['id']} fired but {name(conclusion)} "
                                 f"was already known, so no duplicate was added.")
            fired_rules.append({
                "rule_id": rule["id"], "conclusion": conclusion,
                "conclusion_label": name(conclusion),
                "because": because,
                "because_labels": [name(c) if not c.startswith("not ") else
                                   "not " + name(c[4:]) for c in because],
                "explanation": rule["explanation"],
                "new_fact": is_new, "iteration": iteration,
            })

        if not progressed:
            log("stop", f"Pass {iteration} produced no new facts, so reasoning stops "
                        f"(a fixed point was reached).")
            break
    else:
        hit_limit = True
        log("stop", f"Safety limit of {max_iterations} passes reached; reasoning stopped.")

    # Explain why every rule that never fired could not fire.
    not_fired = []
    for rule in rules:
        if rule["id"] in fired_ids:
            continue
        check = _check_rule(rule, facts, absent, unknown)
        reasons = []
        if check["contradicted"]:
            reasons.append("blocked by answers: " + names(check["contradicted"]))
        if check["unknown"]:
            reasons.append("Not Sure: " + names(check["unknown"]))
        if check["missing"]:
            reasons.append("not established: " + names(check["missing"]))
        not_fired.append({
            "rule_id": rule["id"], "conclusion": rule["then"],
            "conclusion_label": name(rule["then"]),
            "status": check["status"], "reasons": reasons,
        })

    # Full rule-by-rule report: every rule, every condition, and its state.
    #   met             - condition satisfied
    #   failed          - answered the opposite way (a required symptom is
    #                     absent, or a must-be-absent symptom is present)
    #   unknown         - answered Not Sure (never counts as support)
    #   not_established - never answered / not derived by any fired rule
    def condition_state(cond, need):
        if need == "present":
            if cond in facts:
                return "met"
            if cond in absent:
                return "failed"
        else:
            if cond in absent:
                return "met"
            if cond in facts:
                return "failed"
        return "unknown" if cond in unknown else "not_established"

    rule_report = []
    for rule in rules:
        conditions = [{"fact": c, "label": name(c), "need": "present",
                       "state": condition_state(c, "present")} for c in rule["if"]]
        conditions += [{"fact": c, "label": name(c), "need": "absent",
                        "state": condition_state(c, "absent")}
                       for c in rule.get("if_absent", [])]
        rule_report.append({
            "rule_id": rule["id"], "conclusion": rule["then"],
            "conclusion_label": name(rule["then"]),
            "explanation": rule["explanation"],
            "fired": rule["id"] in fired_ids,
            "conditions": conditions,
        })

    final_facts = sorted(facts)
    derived = [f for f in final_facts if f not in set(initial_facts)]
    patterns = [p for p in pattern_ids if p in facts]

    return {
        "algorithm": "forward_chaining",
        "initial_facts": initial_facts,
        "final_facts": final_facts,
        "derived_facts": derived,
        "fired_rules": fired_rules,
        "not_fired_rules": not_fired,
        "rule_report": rule_report,
        "patterns": patterns,
        "iterations": iterations,
        "hit_iteration_limit": hit_limit,
        "trace": trace,
    }
