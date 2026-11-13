"""Local server for demo.html (stdlib only).

    python demo_server.py                                   # Judge 1 criterion
    python demo_server.py --criterion surprise/CRITERION.md --dev surprise/dev_pairs.jsonl
then open http://localhost:8000

Uses the same JUDGE_LLM_* environment variables as run_judge.py.
"""
from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import final_judge as fj

ap = argparse.ArgumentParser()
ap.add_argument("--criterion", default="JUDGE1_CRITERION.md")
ap.add_argument("--policy", default="policy.md")
ap.add_argument("--dev", default="dev_pairs.jsonl")
ap.add_argument("--html", default="demo.html")
ap.add_argument("--port", type=int, default=8000)
args = ap.parse_args()

CRITERION = open(args.criterion, encoding="utf-8").read()
POLICY = open(args.policy, encoding="utf-8").read()
DEV = [json.loads(l) for l in open(args.dev, encoding="utf-8") if l.strip()] if os.path.exists(args.dev) else []
fj.prepare(CRITERION, POLICY, DEV)


def judge_detailed(question, reply, lang, criterion, policy) -> dict:
    """Same two-step logic as final_judge.judge(), but also returns the model's reasoning.
    Works with any final_judge version that defines ANALYZE, VERIFY and _verdict."""
    if hasattr(fj, "judge_detailed"):
        return fj.judge_detailed(question, reply, lang, criterion, policy)
    fields = dict(criterion=criterion.strip(), policy=policy.strip(), lang=lang, question=question, reply=reply)
    analysis = fj.complete(fj.ANALYZE.format(examples=fj._examples_text(), **fields))
    if fj._verdict(analysis) == "pass":
        return {"verdict": "pass", "analysis": analysis, "verification": None, "calls": 1}
    check = fj.complete(fj.VERIFY.format(analysis=(analysis or "")[-3000:], **fields))
    return {"verdict": "fail" if fj._verdict(check) == "fail" else "pass",
            "analysis": analysis, "verification": check, "calls": 2}


def ready() -> bool:
    return all(os.environ.get(k) for k in ("JUDGE_LLM_BASE_URL", "JUDGE_LLM_API_KEY", "JUDGE_LLM_MODEL"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html", "/demo.html"):
            self._send(200, open(args.html, "rb").read(), "text/html; charset=utf-8")
        elif self.path == "/api/config":
            self._json(200, {"model": os.environ.get("JUDGE_LLM_MODEL", "not set"), "ready": ready(),
                             "criterion": CRITERION, "policy": POLICY})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/judge":
            return self._json(404, {"error": "not found"})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if not _s(data.get("reply")):
                return self._json(400, {"error": "Reply is empty."})
            out = judge_detailed(_s(data.get("question")), _s(data.get("reply")), _s(data.get("lang")) or "en",
                                    _s(data.get("criterion")) or CRITERION, _s(data.get("policy")) or POLICY)
            out["model"] = os.environ.get("JUDGE_LLM_MODEL", "")
            self._json(200, out)
        except Exception as e:  # show the error in the page instead of a blank failure
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *a):
        print("  " + fmt % a)


def _s(x) -> str:
    return str(x or "").strip()


if __name__ == "__main__":
    print(f"criterion: {args.criterion} | dev examples: {len(DEV)} | LLM configured: {ready()}")
    print(f"open http://localhost:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
