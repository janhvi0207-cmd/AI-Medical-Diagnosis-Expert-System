/*
 * AI Medical Diagnosis System - frontend logic (vanilla JavaScript).
 *
 * One file serves every page; document.body.dataset.page selects the code:
 *   "home"       -> nothing to do
 *   "assessment" -> questionnaire, review, submit to /api/assess
 *   "results"    -> render the JSON the backend returned
 *
 * Privacy: answers live only in memory and in this tab's sessionStorage
 * (cleared when the tab closes or on Restart). Nothing is sent anywhere
 * except to our own /api/assess endpoint.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "assessmentResult";
  var ANSWER_LABELS = { yes: "Yes", no: "No", unsure: "Not Sure" };

  // ---------------------------------------------------------------- helpers
  function $(id) { return document.getElementById(id); }

  // Build DOM safely (textContent only, never innerHTML with data).
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "class") node.className = attrs[k];
        else if (k === "text") node.textContent = attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    (children || []).forEach(function (c) {
      if (c === null || c === undefined) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function show(id) { $(id).hidden = false; }
  function hide(id) { $(id).hidden = true; }

  function storageSet(value) {
    try { sessionStorage.setItem(STORAGE_KEY, value); return true; } catch (e) { return false; }
  }
  function storageGet() {
    try { return sessionStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }
  function storageClear() {
    try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
  }

  // ------------------------------------------------------------ assessment
  function initAssessment() {
    var state = {
      questions: [],      // [{id,label,question,hint,group,emergency}]
      answers: {},        // id -> "yes" | "no" | "unsure"
      index: 0,
      fromReview: false,  // true when editing a single answer from the review screen
      emergencyMessage: ""
    };

    function allViews() {
      ["view-boot", "view-question", "view-review", "view-loading", "view-error"].forEach(hide);
    }

    function answeredCount() {
      return state.questions.filter(function (q) { return state.answers[q.id]; }).length;
    }

    function updateEmergencyBanner() {
      var triggered = state.questions.some(function (q) {
        return q.emergency && state.answers[q.id] === "yes";
      });
      $("emergency-banner").hidden = !triggered;
      if (triggered) $("emergency-text").textContent = state.emergencyMessage;
    }

    function renderQuestion() {
      var q = state.questions[state.index];
      var total = state.questions.length;
      allViews();
      show("view-question");

      $("progress-text").textContent = "Question " + (state.index + 1) + " of " + total;
      $("group-tag").textContent = q.group;
      var pct = Math.round((state.index / total) * 100);
      $("progress-fill").style.width = pct + "%";
      var bar = $("progress-bar");
      bar.setAttribute("aria-valuenow", String(pct));
      bar.setAttribute("aria-label", "Assessment progress");

      $("question-text").textContent = q.question;
      $("question-hint").textContent = q.hint || "";

      var box = $("options");
      box.textContent = "";
      ["yes", "no", "unsure"].forEach(function (value) {
        var inputId = "opt-" + value;
        var input = el("input", { type: "radio", name: "answer", id: inputId, value: value });
        if (state.answers[q.id] === value) input.checked = true;
        input.addEventListener("change", function () {
          state.answers[q.id] = value;
          updateEmergencyBanner();
          syncNav();
        });
        box.appendChild(el("div", { class: "option option-" + value }, [
          input,
          el("label", { for: inputId, text: ANSWER_LABELS[value] })
        ]));
      });

      $("btn-back").hidden = false;
      $("btn-back").disabled = state.index === 0 && !state.fromReview;
      $("btn-review-jump").hidden = !(answeredCount() === total && !state.fromReview);
      syncNav();
      var checked = box.querySelector("input:checked") || box.querySelector("input");
      if (checked) checked.focus({ preventScroll: true });
    }

    function syncNav() {
      var q = state.questions[state.index];
      var answered = Boolean(state.answers[q.id]);
      var last = state.index === state.questions.length - 1;
      var next = $("btn-next");
      next.disabled = !answered;
      next.textContent = state.fromReview ? "Back to review"
                       : last ? "Review Answers" : "Next";
      $("answer-needed").hidden = answered;
    }

    function renderReview() {
      allViews();
      show("view-review");
      var counts = { yes: 0, no: 0, unsure: 0 };
      var list = $("review-list");
      list.textContent = "";
      var lastGroup = "";

      state.questions.forEach(function (q, i) {
        var a = state.answers[q.id];
        counts[a] += 1;
        if (q.group !== lastGroup) {
          list.appendChild(el("h3", { class: "review-group", text: q.group }));
          lastGroup = q.group;
        }
        var edit = el("button", { type: "button", class: "link-btn", text: "Change" });
        edit.setAttribute("aria-label", "Change answer for " + q.label);
        edit.addEventListener("click", function () {
          state.index = i;
          state.fromReview = true;
          renderQuestion();
        });
        list.appendChild(el("div", { class: "review-row" }, [
          el("span", { class: "review-label", text: q.label }),
          el("span", { class: "badge badge-" + a, text: ANSWER_LABELS[a] }),
          edit
        ]));
      });

      var chips = $("review-counts");
      chips.textContent = "";
      chips.appendChild(el("span", { class: "chip", text: counts.yes + " Yes" }));
      chips.appendChild(el("span", { class: "chip", text: counts.no + " No" }));
      chips.appendChild(el("span", { class: "chip", text: counts.unsure + " Not Sure" }));
      $("progress-fill").style.width = "100%";
      window.scrollTo(0, 0);
    }

    function restart() {
      state.answers = {};
      state.index = 0;
      state.fromReview = false;
      storageClear();
      updateEmergencyBanner();
      renderQuestion();
      window.scrollTo(0, 0);
    }

    function showError(message, details) {
      allViews();
      show("view-error");
      $("error-text").textContent = message;
      var ul = $("error-details");
      ul.textContent = "";
      (details || []).forEach(function (d) { ul.appendChild(el("li", { text: d })); });
    }

    function submit() {
      // Final client-side validation: every question must have an answer.
      var missing = state.questions.filter(function (q) { return !state.answers[q.id]; });
      if (missing.length) {
        state.index = state.questions.indexOf(missing[0]);
        state.fromReview = false;
        renderQuestion();
        return;
      }
      allViews();
      show("view-loading");

      fetch("/api/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: state.answers })
      }).then(function (res) {
        return res.json().then(function (body) { return { ok: res.ok, body: body }; });
      }).then(function (r) {
        if (!r.ok) {
          showError((r.body && r.body.error) || "The server rejected the request.",
                    r.body && r.body.details);
          return;
        }
        if (!storageSet(JSON.stringify(r.body))) {
          showError("Your browser blocked temporary session storage, so the results cannot be shown.", []);
          return;
        }
        window.location.href = "/results";
      }).catch(function () {
        showError("Could not reach the server. Check that the Flask app is still running and try again.", []);
      });
    }

    // ---- wire up buttons
    $("btn-next").addEventListener("click", function () {
      var q = state.questions[state.index];
      if (!state.answers[q.id]) return; // validation: an answer is required
      if (state.fromReview) { state.fromReview = false; renderReview(); return; }
      if (state.index < state.questions.length - 1) { state.index += 1; renderQuestion(); }
      else renderReview();
    });
    $("btn-back").addEventListener("click", function () {
      if (state.fromReview) { state.fromReview = false; renderReview(); return; }
      if (state.index > 0) { state.index -= 1; renderQuestion(); }
    });
    $("btn-review-jump").addEventListener("click", renderReview);
    $("btn-restart").addEventListener("click", restart);
    $("btn-restart-review").addEventListener("click", restart);
    $("btn-review-back").addEventListener("click", function () {
      state.index = state.questions.length - 1;
      state.fromReview = false;
      renderQuestion();
    });
    $("btn-submit").addEventListener("click", submit);
    $("btn-retry").addEventListener("click", submit);
    $("btn-error-back").addEventListener("click", renderReview);

    // ---- load questions
    fetch("/api/questions").then(function (res) {
      if (!res.ok) throw new Error("bad status");
      return res.json();
    }).then(function (data) {
      state.emergencyMessage = data.emergency_message;
      state.questions = data.emergency_signs.map(function (e) {
        return { id: e.id, label: e.label, question: e.question, hint: e.hint,
                 group: "Urgent warning signs", emergency: true };
      }).concat(data.symptoms.map(function (s) {
        return { id: s.id, label: s.label, question: s.question, hint: s.hint,
                 group: "Symptoms", emergency: false };
      }));
      renderQuestion();
    }).catch(function () {
      allViews();
      show("view-error");
      $("error-text").textContent = "Could not load the questions. Is the Flask server running?";
      $("btn-retry").hidden = true;
      $("btn-error-back").hidden = true;
    });
  }

  // --------------------------------------------------------------- results
  function chips(items, cls) {
    var wrap = el("div", { class: "chips" });
    items.forEach(function (t) { wrap.appendChild(el("span", { class: "chip " + (cls || ""), text: t })); });
    return wrap;
  }

  function card(title, children, cls) {
    return el("section", { class: "panel " + (cls || "") }, [el("h2", { text: title })].concat(children));
  }

  function statusBadge(status, label) {
    return el("span", { class: "badge badge-" + status, text: label });
  }

  var STATE_TEXT = {
    met: "Met",
    unknown: "Not Sure (not counted as support)",
    not_established: "Not established"
  };

  // One line per rule condition, e.g. "Fever (must be absent) - Met".
  function conditionList(conditions) {
    return el("ul", { class: "cond-list" }, conditions.map(function (c) {
      var label = c.need === "absent" ? c.label + " (must be absent)" : c.label;
      var text = STATE_TEXT[c.state];
      if (c.state === "failed") {
        text = c.need === "absent" ? "Failed: this symptom is present"
                                   : "Failed: answered No";
      }
      if (c.state === "not_established" && c.how) text += " - needs " + c.how;
      return el("li", { class: "cond cond-" + c.state }, [
        el("span", { class: "cond-label", text: label }),
        el("span", { class: "cond-state", text: text })
      ]);
    }));
  }

  function renderTrace(trace, indented) {
    var list = el("ol", { class: "trace" });
    trace.forEach(function (t) {
      var li = el("li", { class: "trace-item trace-" + t.kind, text: t.text });
      if (indented) li.style.marginLeft = (t.depth * 14) + "px";
      list.appendChild(li);
    });
    return list;
  }

  function renderResults(data) {
    var L = data.labels;
    var name = function (id) { return L[id] || id; };
    var root = $("results-root");
    root.textContent = "";

    // 1. Emergency guidance always comes first and is never overridden.
    if (data.emergency.triggered) {
      root.appendChild(el("div", { class: "alert alert-danger", role: "alert" }, [
        el("strong", { text: "Urgent guidance: seek emergency care now" }),
        el("p", { text: data.emergency.message }),
        el("p", { text: "Warning sign(s) reported: " +
                   data.emergency.signs.map(function (s) { return s.label; }).join(", ") + "." })
      ]));
    } else if (data.emergency.unsure_signs.length) {
      root.appendChild(el("div", { class: "alert alert-warn", role: "note" }, [
        el("strong", { text: "You were not sure about some warning signs" }),
        el("p", { text: "Not sure about: " +
                   data.emergency.unsure_signs.map(function (s) { return s.label; }).join(", ") +
                   ". If any of these may apply, seek medical help promptly." })
      ]));
    }

    // 2. Summary
    var c = data.summary.counts;
    root.appendChild(el("section", { class: "panel summary" }, [
      el("p", { class: "eyebrow", text: "Assessment summary" }),
      el("h1", { text: data.summary.headline }),
      el("p", { class: "lead", text: data.summary.detail }),
      chips([c.yes + " Yes", c.no + " No", c.unsure + " Not Sure"]),
      el("p", { class: "muted small", text: data.disclaimer })
    ]));

    // 3. Patterns
    var supported = data.patterns.filter(function (p) { return p.forward_supported; });
    var others = data.patterns.filter(function (p) { return !p.forward_supported; });
    var patternNodes = [];
    if (!supported.length) {
      patternNodes.push(el("div", { class: "empty-note" }, [
        el("strong", { text: "No supported symptom pattern was found." }),
        el("p", { text: "None of the example rules were fully satisfied by your answers. " +
                        "That does not mean nothing is wrong. Speak to a professional if you are concerned." })
      ]));
    }
    supported.forEach(function (p) {
      var kids = [
        el("div", { class: "pattern-head" }, [
          el("h3", { text: p.label }),
          statusBadge("supported", "Supported by rules")
        ]),
        el("p", { class: "muted", text: p.description }),
        el("p", { class: "small-label", text: "Symptoms supporting this pattern" }),
        chips(p.supporting_symptoms.map(function (s) { return s.label; }), "chip-teal"),
        el("p", { class: "muted small", text: "Rules used: " + p.rules_used.join(", ") +
                  ". Backward chaining: " + p.backward_status_label + "." })
      ];
      patternNodes.push(el("article", { class: "pattern-card" }, kids));
    });
    if (others.length) {
      patternNodes.push(el("p", { class: "small-label", text: "Patterns not supported by your answers" }));
      others.forEach(function (p) {
        var kids = [
          el("div", { class: "pattern-head" }, [
            el("h3", { text: p.label }),
            statusBadge(p.backward_status, p.backward_status_label)
          ])
        ];
        if (p.closest_rule) {
          kids.push(el("p", { class: "muted small",
            text: "Closest rule: " + p.closest_rule.rule_id + " - " + p.closest_rule.explanation }));
          kids.push(conditionList(p.closest_rule.conditions));
        }
        patternNodes.push(el("article", { class: "pattern-card pattern-card-muted" }, kids));
      });
    }
    patternNodes.push(el("p", { class: "muted small",
      text: "These are educational possibilities from illustrative rules, not diagnoses. " +
            "No percentages or confidence scores are given because the rules are not statistical." }));
    root.appendChild(card("Possible symptom patterns", patternNodes));

    // 4. Answers: present / absent / unknown + information gaps
    var cols = [
      ["Present (answered Yes)", data.answers.present, "chip-teal"],
      ["Absent (answered No)", data.answers.absent, ""],
      ["Unknown (answered Not Sure)", data.answers.unknown, "chip-warn"]
    ].map(function (c3) {
      return el("div", { class: "col" }, [
        el("p", { class: "small-label", text: c3[0] }),
        c3[1].length ? chips(c3[1].map(function (s) { return s.label; }), c3[2])
                     : el("p", { class: "muted small", text: "None" })
      ]);
    });
    var gapNodes = [el("div", { class: "three-col" }, cols)];
    var gaps = data.backward.filter(function (b) {
      return b.status === "inconclusive" && b.unknown_conditions.length;
    });
    if (gaps.length) {
      gapNodes.push(el("p", { class: "small-label", text: "Missing information that blocked a conclusion" }));
      gaps.forEach(function (b) {
        gapNodes.push(el("p", { text: b.goal_label + ": Not Sure about " +
          b.unknown_conditions.map(name).join(", ") + "." }));
      });
    }
    gapNodes.push(el("p", { class: "muted small",
      text: "A Not Sure answer is never counted as support, and it is different from No." }));
    root.appendChild(card("Your answers and missing information", gapNodes));

    // 5. Forward chaining
    var f = data.forward;
    var fwdNodes = [
      el("p", { class: "muted",
        text: "Data-driven: start from the known facts, fire every rule whose conditions are met, " +
              "and repeat until nothing new can be inferred." }),
      el("p", { class: "small-label", text: "Starting facts" }),
      f.initial_facts.length ? chips(f.initial_facts.map(name), "chip-teal")
                             : el("p", { class: "muted small", text: "None" }),
      el("p", { class: "small-label", text: "Rules fired (" + f.fired_rules.length + ")" })
    ];
    if (f.fired_rules.length) {
      fwdNodes.push(el("ul", { class: "plain-list" }, f.fired_rules.map(function (r) {
        return el("li", { text: r.rule_id + ": " + r.because_labels.join(" + ") + " → " +
          r.conclusion_label + (r.new_fact ? "" : " (already known)") });
      })));
    } else {
      fwdNodes.push(el("p", { class: "muted small", text: "No rule fired." }));
    }
    fwdNodes.push(el("p", { class: "small-label", text: "Patterns derived" }));
    fwdNodes.push(f.patterns.length ? chips(f.patterns.map(name), "chip-teal")
                                    : el("p", { class: "muted small", text: "None" }));
    if (f.not_fired_rules.length) {
      var nf = f.not_fired_rules.map(function (r) {
        return el("li", { text: r.rule_id + " (" + r.conclusion_label + "): " +
          (r.reasons.join("; ") || r.status) });
      });
      fwdNodes.push(el("details", {}, [
        el("summary", { text: "Rules that did not fire (" + f.not_fired_rules.length + ") and why" }),
        el("ul", { class: "plain-list" }, nf)
      ]));
    }
    // Rule-by-rule report: fired rules first, then those that did not fire.
    var report = f.rule_report.slice().sort(function (a, b) {
      return (b.fired ? 1 : 0) - (a.fired ? 1 : 0);
    });
    fwdNodes.push(el("details", { open: "open" }, [
      el("summary", { text: "Rule-by-rule report: which rules fired and which conditions failed" }),
      el("div", { class: "rule-report" }, report.map(function (r) {
        return el("article", { class: "rule-card " + (r.fired ? "rule-fired" : "rule-not-fired") }, [
          el("div", { class: "pattern-head" }, [
            el("strong", { text: r.rule_id + " → " + r.conclusion_label }),
            statusBadge(r.fired ? "supported" : "unsupported", r.fired ? "Fired" : "Did not fire")
          ]),
          el("p", { class: "muted small", text: r.explanation }),
          conditionList(r.conditions)
        ]);
      }))
    ]));
    var fwdTrace = el("details", { open: "open" }, [
      el("summary", { text: "Step-by-step reasoning trace (" + f.trace.length + " steps)" }),
      renderTrace(f.trace, false)
    ]);
    fwdNodes.push(fwdTrace);
    if (f.hit_iteration_limit) {
      fwdNodes.push(el("p", { class: "muted small", text: "The safety iteration limit was reached." }));
    }
    root.appendChild(card("Forward chaining results", fwdNodes));

    // 6. Backward chaining
    var bwdNodes = [el("p", { class: "muted",
      text: "Goal-driven: take each pattern as a hypothesis and work backwards to see whether " +
            "the answers can establish it." })];
    data.backward.forEach(function (b) {
      // A shared sub-goal can be re-proved under several rules, so list each rule once.
      var evaluatedIds = [];
      b.rules_evaluated.forEach(function (r) {
        if (evaluatedIds.indexOf(r.rule_id) === -1) evaluatedIds.push(r.rule_id);
      });
      var evaluated = evaluatedIds.join(", ") || "none";
      bwdNodes.push(el("article", { class: "pattern-card" }, [
        el("div", { class: "pattern-head" }, [
          el("h3", { text: "Hypothesis: " + b.goal_label }),
          statusBadge(b.status, b.status_label)
        ]),
        el("p", { text: b.explanation }),
        el("p", { class: "muted small", text: "Rules evaluated: " + evaluated }),
        b.absent_conditions.length ? el("p", { class: "muted small",
          text: "Absent conditions met: " + b.absent_conditions.map(name).join(", ") }) : null,
        b.unknown_conditions.length ? el("p", { class: "muted small",
          text: "Unknown conditions: " + b.unknown_conditions.map(name).join(", ") }) : null,
        el("details", { open: "open" }, [
          el("summary", { text: "Step-by-step reasoning trace (" + b.trace.length + " steps)" }),
          renderTrace(b.trace, true)
        ])
      ]));
    });
    root.appendChild(card("Backward chaining results", bwdNodes));

    // 7. Comparison
    var cmp = data.comparison;
    var table = el("table", { class: "compare" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: "Aspect" }), el("th", { text: "Forward chaining" }),
        el("th", { text: "Backward chaining" })])]),
      el("tbody", {}, cmp.points.map(function (p) {
        return el("tr", {}, [
          el("th", { scope: "row", text: p.aspect }),
          el("td", { text: p.forward }), el("td", { text: p.backward })]);
      }))
    ]);
    root.appendChild(card("How the two algorithms differ", [
      el("div", { class: "table-wrap" }, [table]),
      el("p", { text: cmp.this_run }),
      el("p", { class: "muted small", text: cmp.agree
        ? "On this assessment both algorithms reached the same conclusions for every pattern."
        : "On this assessment the algorithms disagreed on at least one pattern." })
    ]));

    // 8. Safety + restart
    var safetyList = el("ul", {}, data.safety.map(function (s) { return el("li", { text: s }); }));
    var restart = el("a", { class: "btn", href: "/assessment", text: "Start a new assessment" });
    restart.addEventListener("click", storageClear);
    root.appendChild(card("Safety information", [safetyList, restart], "safety-panel"));

    root.hidden = false;
    $("results-empty").hidden = true;
  }

  function initResults() {
    var raw = storageGet();
    var data = null;
    if (raw) { try { data = JSON.parse(raw); } catch (e) { data = null; } }
    if (!data || !data.patterns || !data.forward) {
      $("results-empty").hidden = false;
      return;
    }
    renderResults(data);
  }

  // ---------------------------------------------------------------- start
  var page = document.body.getAttribute("data-page");
  if (page === "assessment") initAssessment();
  else if (page === "results") initResults();
})();
