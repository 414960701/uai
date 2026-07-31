#!/usr/bin/env python3
"""Local-only HTTP fixture for browser/control-plane journey tests.

This process is never registered as a UAI Forge provider and never logs
request headers or bodies.  It lets a browser test exercise the real OpenAI-
compatible adapter without a network account or a production catalog change.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "UAIForgeProviderFixture/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        del format, args

    def _write(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/models", "/v1/models"}:
            self._write(
                200,
                {
                    "object": "list",
                    "data": [{"id": "fixture-model", "object": "model", "owned_by": "uai-forge"}],
                },
            )
            return
        self._write(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._write(400, {"error": {"message": "invalid json"}})
            return

        if self.path in {"/chat/completions", "/v1/chat/completions"}:
            messages = payload.get("messages") or []
            prompt = messages[-1].get("content", "") if messages else ""
            self._write(
                200,
                {
                    "id": "fixture-chat-1",
                    "model": payload.get("model", "fixture-model"),
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": f"fixture: {prompt}"},
                        }
                    ],
                    "usage": {"prompt_tokens": 8, "completion_tokens": 6},
                },
            )
            return

        if self.path == "/v1/messages":
            messages = payload.get("messages") or []
            prompt = messages[-1].get("content", "") if messages else ""
            self._write(
                200,
                {
                    "id": "fixture-message-1",
                    "model": payload.get("model", "fixture-model"),
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": f"fixture: {prompt}"}],
                    "usage": {"input_tokens": 8, "output_tokens": 6},
                },
            )
            return

        self._write(404, {"error": {"message": "not found"}})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), FixtureHandler)
    print(f"provider fixture listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
