# Local demo UI

The demo is a small local web app for presenting and manually trying the single-reply judge.
It uses only Python's standard library and calls `final_judge.py` directly.

From the project root, activate the existing virtual environment and start the app:

```powershell
cd starter_pack
python demo_app.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The app reads `.env` from the project root.
Set `JUDGE_LLM_BASE_URL`, `JUDGE_LLM_API_KEY`, and `JUDGE_LLM_MODEL=claude-haiku-4.5` before judging.
The key stays on the server and is never returned to the browser. Requests are handled on localhost.

Choose a built-in example or enter a customer question and one reply. The result panel shows the judge's
analysis and, when the judge calls its verifier, that response too. Criterion and policy text can be edited
in the side panel for an input-only rubric experiment. The UI does not save review text.

Stop the server with `Ctrl+C` in the terminal.
