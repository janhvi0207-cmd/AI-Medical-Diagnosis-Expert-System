"""
Backward chaining (GOAL-DRIVEN reasoning).

Idea: start from a HYPOTHESIS (a goal) and work backwards. To prove the goal,
find the rules that conclude it and try to prove each of their conditions,
which are themselves treated as sub-goals (recursion).

    goal --> which rules conclude it? --> prove each condition --> ...

Each goal ends in one of three outcomes:
    supported     - some rule has every condition proved
    unsupported   - every rule that could prove it is contradicted by the answers
    inconclusive  - no rule is fully proved, but at least one rule is blocked
                    only by Not Sure / unanswered information

A "Not Sure" answer never counts as support. If an unknown condition blocks
one rule but ANOTHER rule is fully proved, the goal is still supported.

Loop protection: the set `path` holds the goals currently being proved on this
branch. Meeting a goal already in `path` means the rules are circular, so that
branch is treated as unsupported instead of recursing forever. `max_depth`
is a second safety net.
"""

SUPPORTED = "supported"
UNSUPPORTED = "unsupported"
INCONCLUSIVE = "inconclusive"

STATUS_LABELS = {
    SUPPORTED: "Supported by the entered answers",
    UNSUPPORTED: "Not supported by the entered answers",
    INCONCLUSIVE: "Inconclusive - more information needed",
}


def backward_chain(goal, present, absent, unknown, rules, labels=None, max_depth=25):
    """
    Try to prove `goal` from the given facts.

    goal                     : fact id to prove, e.g. "pattern_flu_like"
    present, absent, unknown : iterables of fact ids (the three answer states)
    rules                    : list of rule dicts (see knowledge_base.py)
    labels                   : optional {id: readable name} for the trace

    Returns a dict with the status, reasoning trace, rules evaluated and the
    facts used / absent / unknown / unanswered conditions that were met.
    """
    labels = labels or {}
    name = lambda fid: labels.get(fid, fid)  # noqa: E731

    present, absent, unknown = set(present), set(absent), set(unknown)

    # Index rules by what they conclude, so "which rules prove G?" is instant.
    by_conclusion = {}
    for rule in rules:
        by_conclusion.setdefault(rule["then"], []).append(rule)

    trace = []
    rules_evaluated = []
    facts_used, absent_hit, unknown_hit = [], [], []
    unanswered, cycles = [], []

    def add_unique(bucket, value):
        if value not in bucket:
            bucket.append(value)

    def log(depth, kind, text):
        trace.append({"depth": depth, "kind": kind, "text": text})

    def prove(g, path, depth):
        """Return SUPPORTED / UNSUPPORTED / INCONCLUSIVE for goal g."""
        # 1. Direct knowledge about g.
        if g in present:
            add_unique(facts_used, g)
            log(depth, "fact", f"{name(g)} is a known fact (answered Yes).")
            return SUPPORTED
        if g in absent:
            add_unique(absent_hit, g)
            log(depth, "absent", f"{name(g)} is explicitly absent (answered No).")
            return UNSUPPORTED
        if g in unknown:
            add_unique(unknown_hit, g)
            log(depth, "unknown", f"{name(g)} is unknown (answered Not Sure), "
                                  f"so it cannot be used as support.")
            return INCONCLUSIVE

        # 2. Loop / runaway-recursion protection.
        if g in path:
            add_unique(cycles, g)
            log(depth, "cycle", f"Circular reasoning detected at {name(g)}; "
                                f"this branch is abandoned.")
            return UNSUPPORTED
        if depth > max_depth:
            log(depth, "limit", f"Depth limit reached at {name(g)}.")
            return INCONCLUSIVE

        # 3. Find the rules that could establish g.
        candidates = by_conclusion.get(g, [])
        if not candidates:
            # A base symptom with no answer at all: no information either way.
            add_unique(unanswered, g)
            log(depth, "missing", f"No answer exists for {name(g)} and no rule "
                                  f"can derive it.")
            return INCONCLUSIVE

        ids = ", ".join(r["id"] for r in candidates)
        log(depth, "goal", f"Goal: establish {name(g)}. "
                           f"Rule(s) that conclude it: {ids}.")

        new_path = path | {g}      # the visited-goal set for this branch
        outcome = UNSUPPORTED

        for rule in candidates:
            record = {"rule_id": rule["id"], "conclusion": g,
                      "conclusion_label": name(g), "status": None}
            rules_evaluated.append(record)
            needs = [name(c) for c in rule["if"]] + \
                    [f"no {name(c)}" for c in rule.get("if_absent", [])]
            log(depth + 1, "rule", f"Try rule {rule['id']}: needs {', '.join(needs)}.")

            rule_status = SUPPORTED
            for cond in rule["if"]:
                s = prove(cond, new_path, depth + 2)
                if s == UNSUPPORTED:
                    rule_status = UNSUPPORTED
                    break                      # one failed condition is enough
                if s == INCONCLUSIVE:
                    rule_status = INCONCLUSIVE  # keep going to collect unknowns

            if rule_status != UNSUPPORTED:
                for cond in rule.get("if_absent", []):
                    log(depth + 2, "negation", f"Condition: {name(cond)} must be absent.")
                    s = prove(cond, new_path, depth + 3)
                    # Negate: proving the symptom present kills the rule;
                    # proving it absent satisfies the condition.
                    if s == SUPPORTED:
                        rule_status = UNSUPPORTED
                        break
                    if s == INCONCLUSIVE:
                        rule_status = INCONCLUSIVE

            record["status"] = rule_status
            verdict = {SUPPORTED: "all conditions satisfied",
                       UNSUPPORTED: "a condition failed",
                       INCONCLUSIVE: "blocked by unknown/unanswered information"}[rule_status]
            log(depth + 1, "rule_result", f"Rule {rule['id']}: {verdict}.")

            if rule_status == SUPPORTED:
                outcome = SUPPORTED
                break                          # one complete rule is enough
            if rule_status == INCONCLUSIVE:
                outcome = INCONCLUSIVE         # may still be rescued by a later rule

        log(depth, "result", f"{name(g)} is {outcome}.")
        return outcome

    status = prove(goal, frozenset(), 0)

    if status == SUPPORTED:
        explanation = (f"At least one rule for {name(goal)} has all of its "
                       f"conditions satisfied by your answers.")
    elif status == INCONCLUSIVE:
        explanation = (f"No complete rule was found for {name(goal)}, but some "
                       f"conditions were Not Sure or unanswered, so it cannot be "
                       f"rejected either.")
    else:
        explanation = (f"Every rule for {name(goal)} is contradicted by "
                       f"answers you gave (or has no way to be satisfied).")

    return {
        "algorithm": "backward_chaining",
        "goal": goal,
        "goal_label": name(goal),
        "status": status,
        "status_label": STATUS_LABELS[status],
        "explanation": explanation,
        "rules_evaluated": rules_evaluated,
        "facts_used": facts_used,
        "absent_conditions": absent_hit,
        "unknown_conditions": unknown_hit,
        "unanswered_conditions": unanswered,
        "cycles_detected": cycles,
        "trace": trace,
    }
