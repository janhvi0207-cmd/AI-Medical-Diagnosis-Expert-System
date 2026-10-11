# AI Medical Diagnosis System (educational)

A college AI laboratory project: a Flask web app with a rule-based expert system that
demonstrates **forward chaining** and **backward chaining** on a few illustrative symptom
patterns (cold-like, flu-like, allergy-like).

> **Educational use only.** This is not a medical device. It cannot diagnose, confirm or rule
> out any condition. The rules are small illustrative examples and are **not medically
> validated**. Answers are processed in memory only; nothing is stored or sent externally.

## Run it (Windows PowerShell, VS Code terminal)

```powershell
# 1. Go to the project folder
cd C:\Users\hp\AI-Medical-Diagnosis-Web

# 2. Create a virtual environment (once)
python -m venv .venv

# 3. Activate it
.\.venv\Scripts\Activate.ps1
#    If PowerShell blocks scripts, run this once, then activate again:
#    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the app, then open http://127.0.0.1:5000
python app.py

# 6. Run the automated tests (in a second terminal, with the venv active)
python -m unittest discover tests -v
```

Stop the server with `Ctrl + C`.

### Troubleshooting

| Problem | Fix |
|---|---|
| `Activate.ps1 cannot be loaded` | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then activate again |
| `Address already in use` (port 5000) | An old server is still running. Close its terminal or press `Ctrl + C` there, then start again |
| Page shows old behaviour after you edit a file | The server does not auto-reload. Stop it (`Ctrl + C`), run `python app.py` again, then hard-refresh the browser with `Ctrl + F5` |
| `No module named flask` | The virtual environment is not active. Run the activate command, then `pip install -r requirements.txt` |

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask routes, request validation, answers -> facts, emergency check, runs both engines |
| `engine/knowledge_base.py` | DATA only: symptoms, emergency signs, derived facts, patterns, rules |
| `engine/forward_chaining.py` | Data-driven algorithm (facts -> rules -> new facts) |
| `engine/backward_chaining.py` | Goal-driven algorithm (goal -> rules -> sub-goals) |
| `templates/` | `base.html` (layout), `index.html` (welcome), `assessment.html`, `results.html` |
| `static/css/style.css` | Navy / teal / white responsive theme |
| `static/js/app.js` | Questionnaire, review, submit, and results rendering |
| `tests/` | `unittest` tests for both engines and the Flask app |

## Data flow

1. `assessment.html` + `app.js` load the questions from `GET /api/questions`.
2. The user answers Yes / No / Not Sure; `app.js` validates and shows a review screen.
3. `POST /api/assess` sends `{"answers": {"fever": "yes", ...}}`.
4. `app.py` validates it, builds facts (present / absent / unknown) and checks emergency signs separately.
5. The **same** facts go to `forward_chain()` and, for each pattern, `backward_chain()`.
6. JSON comes back; `app.js` stores it in this tab's `sessionStorage` and opens `/results`.
7. `results.html` renders the summary, patterns, both traces and the comparison.

## Three answer states

| Answer | Meaning | Effect |
|---|---|---|
| Yes | present | a known fact |
| No | absent | blocks rules needing it; satisfies "must be absent" conditions |
| Not Sure | unknown | never support; forward: rule does not fire; backward: goal inconclusive unless another complete rule supports it |

## Known limitations

- Rules are a classroom example: 12 symptoms, 4 emergency warning signs, 3 patterns, 19 rules.
  They are illustrative and **not clinically validated**; a pattern is never a diagnosis.
- Some answers can match more than one pattern; all matching patterns are shown.
- "Must be absent" conditions may only reference asked symptoms (checked by a test).
- Backward chaining re-proves a shared sub-goal for each rule that needs it (no caching), so a
  rule can appear several times in its trace. This keeps the trace simple to follow.
- Emergency warning signs are checked separately from the rules and are never passed to the engines.
- Automated checks cover the engines, the Flask API, and the JavaScript flow in a simulated
  browser. Visual appearance on real desktop and phone screens should be checked by hand.
