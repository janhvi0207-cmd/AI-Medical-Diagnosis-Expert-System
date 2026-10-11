
# AI Medical Diagnosis Expert System

An educational rule-based expert system demonstrating forward and backward chaining using Python and Flask.

## Educational Disclaimer

This is a college educational project, not a medical device. It cannot diagnose, confirm, or rule out any medical condition. The rules are illustrative examples and are not medically validated. Do not use the results for medical decisions.

Answers are processed in memory during a request and in the browser tab's session storage. No database is used.

## Run It (Windows PowerShell / VS Code)

```powershell
# 1. Go to the project folder
cd C:\Users\hp\AI-Medical-Diagnosis-Web

# 2. Create a virtual environment (once)
python -m venv .venv

# 3. Activate the environment
.\.venv\Scripts\Activate.ps1

# If PowerShell blocks scripts, run this once:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the application
python app.py
```

Open http://127.0.0.1:5000 in your browser.

Stop the server with `Ctrl + C`.

### Run Tests

```powershell
python -m unittest discover tests -v
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Activate.ps1 cannot be loaded` | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then activate again. |
| `Address already in use` | Stop the other server using port 5000, then restart the application. |
| Old behaviour after editing | Restart `python app.py` and hard-refresh with `Ctrl + F5`. |
| `No module named flask` | Activate the virtual environment and run `pip install -r requirements.txt`. |

## Project Structure

| File or folder | Purpose |
|---|---|
| `app.py` | Flask routes, request validation, emergency checks, and engine execution |
| `engine/knowledge_base.py` | Symptoms, emergency signs, derived facts, patterns, and rules |
| `engine/forward_chaining.py` | Data-driven inference algorithm |
| `engine/backward_chaining.py` | Goal-driven inference algorithm |
| `templates/` | HTML templates for the welcome, questionnaire, layout, and results pages |
| `static/css/style.css` | Responsive user interface styling |
| `static/js/app.js` | Questionnaire, review, submission, and results rendering |
| `tests/` | Automated tests for the engines and Flask application |

## How It Works

1. The application loads the questions.
2. The user answers Yes, No, or Not Sure.
3. The application validates the answers and checks emergency warning signs separately.
4. Answers are converted into present, absent, and unknown facts.
5. Forward chaining derives conclusions from known facts.
6. Backward chaining attempts to prove each target pattern.
7. The results page displays the patterns, reasoning traces, and comparison.

## Meaning of Answers

| Answer | Meaning |
|---|---|
| Yes | The symptom is reported as present. |
| No | The symptom is reported as absent. |
| Not Sure | The answer is unknown and is not treated as either Yes or No. |

## Known Limitations

- The knowledge base contains 12 symptoms, 4 emergency warning signs, 3 example patterns, and 19 illustrative rules.
- The rules are not clinically validated, and results are not medical diagnoses.
- One set of answers may support multiple patterns.
- Unknown answers can make results inconclusive.
- Backward chaining may re-check shared sub-goals.
- Emergency warning signs are handled separately from the inference engines.
- Automated tests do not replace manual visual checks in real browsers.
