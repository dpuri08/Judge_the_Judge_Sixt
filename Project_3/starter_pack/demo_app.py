"""Local web demo for the single-reply policy judge (stdlib only).

Run from starter_pack with `python demo_app.py`. The server binds only to localhost,
loads the project .env without returning secrets to the browser, and calls final_judge.
"""
from __future__ import annotations

import importlib.util
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent


def load_env() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env()
spec = importlib.util.spec_from_file_location("project_final_judge", ROOT / "final_judge.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load starter_pack/final_judge.py")
judge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge_module)


def read_inputs() -> tuple[str, str, list[dict]]:
    criterion = (ROOT / "JUDGE1_CRITERION.md").read_text(encoding="utf-8")
    policy = (ROOT / "policy.md").read_text(encoding="utf-8")
    dev_path = ROOT / "dev_pairs.jsonl"
    examples = [json.loads(line) for line in dev_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return criterion, policy, examples


DEFAULT_CRITERION, DEFAULT_POLICY, DEFAULT_EXAMPLES = read_inputs()
judge_module.prepare(DEFAULT_CRITERION, DEFAULT_POLICY, DEFAULT_EXAMPLES)


class Handler(BaseHTTPRequestHandler):
    server_version = "JudgeDemo/1.0"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/config":
            model = os.environ.get("JUDGE_LLM_MODEL", "")
            ready = all(os.environ.get(k) for k in ("JUDGE_LLM_BASE_URL", "JUDGE_LLM_API_KEY", "JUDGE_LLM_MODEL"))
            self._json(200, {"model": model or "not configured", "ready": ready,
                             "criterion": DEFAULT_CRITERION, "policy": DEFAULT_POLICY})
        elif route in ("/", "/index.html"):
            html = (ROOT / "demo.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/judge":
            self._json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 100_000:
                self._json(400, {"error": "Request must be between 1 byte and 100 KB."})
                return
            body = json.loads(self.rfile.read(length))
            question = str(body.get("question", "")).strip()
            reply = str(body.get("reply", "")).strip()
            lang = str(body.get("lang", "en")).strip() or "en"
            criterion = str(body.get("criterion", DEFAULT_CRITERION)).strip()
            policy = str(body.get("policy", DEFAULT_POLICY)).strip()
            examples = body.get("examples") or DEFAULT_EXAMPLES
            if not reply:
                self._json(400, {"error": "Enter a reply to evaluate."})
                return
            if not criterion or not policy:
                self._json(400, {"error": "Criterion and policy are required."})
                return
            if isinstance(examples, str):
                examples = [json.loads(line) for line in examples.splitlines() if line.strip()]
            if not isinstance(examples, list):
                raise ValueError("Examples must be a list of labelled JSONL rows.")

            # The demo server is single-threaded. Refresh the module's prepared examples for these inputs.
            judge_module.prepare(criterion, policy, examples)
            captured: list[str] = []
            original_complete = judge_module.complete

            def capture(prompt: str) -> str:
                answer = original_complete(prompt)
                captured.append(answer or "")
                return answer

            judge_module.complete = capture
            try:
                verdict = judge_module.judge(question, reply, lang, criterion, policy)
            finally:
                judge_module.complete = original_complete
            self._json(200, {
                "verdict": verdict,
                "model": os.environ.get("JUDGE_LLM_MODEL", "not configured"),
                "calls": len(captured),
                "analysis": captured[0] if captured else "",
                "verification": captured[1] if len(captured) > 1 else "",
            })
        except Exception as exc:  # surfaced in UI for local debugging; API key is never included
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt: str, *args) -> None:
        # Keep customer text and prompts out of the terminal log.
        if args and str(args[1]).startswith("5"):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", int(os.environ.get("JUDGE_DEMO_PORT", "8765"))), Handler)
    print(f"Judge the Judge demo is ready at http://127.0.0.1:{server.server_port}")
    print("Press Ctrl+C to stop. Requests stay on this machine; model calls use your configured endpoint.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDemo stopped.")
    finally:
        server.server_close()
