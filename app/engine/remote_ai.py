from __future__ import annotations
import json
import threading
from typing import Optional, Dict, Any, List
import requests

class RemoteAIClient:
    """Simple HTTP client to talk to an external chess AI service.
    This code purposely avoids any OpenAPI tooling; the contract is implicit.
    """
    def __init__(self, base_url: str, api_key: Optional[str] = None,
                 timeout: float = 15.0, verify_tls: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.verify_tls = verify_tls

    def best_move(self, fen: str, history_uci: List[str] | None = None,
                  think_ms: int = 2000, options: Dict[str, Any] | None = None,
                  cancel_event: threading.Event | None = None) -> Dict[str, Any]:
        url = f"{self.base_url}/bestmove"  # minimal REST path
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "fen": fen,
            "history_uci": history_uci or [],
            "think_ms": think_ms,
            "options": options or {}
        }
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload),
                                 timeout=self.timeout, verify=self.verify_tls)
            if cancel_event and cancel_event.is_set():
                return {"cancelled": True}
            if resp.status_code != 200:
                return {"error": f"http_{resp.status_code}", "detail": resp.text}
            data = resp.json()
            mv = data.get("move")
            if not mv:
                return {"error": "no_move", "detail": data}
            data.setdefault("score", {})
            data.setdefault("depth", None)
            data.setdefault("nodes", None)
            data.setdefault("pv", [])
            data.setdefault("elapsed_ms", None)
            return data
        except requests.exceptions.Timeout:
            return {"error": "timeout"}
        except Exception as e:
            return {"error": "exception", "detail": str(e)}

class RemoteAIWorker(threading.Thread):
    """Run remote AI call off the Tk main thread."""
    def __init__(self, client: RemoteAIClient, fen: str, history_uci: list[str],
                 outq, think_ms: int = 2000):
        super().__init__(daemon=True)
        self.client = client
        self.fen = fen
        self.history_uci = history_uci
        self.outq = outq
        self.think_ms = think_ms
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        res = self.client.best_move(
            fen=self.fen,
            history_uci=self.history_uci,
            think_ms=self.think_ms,
            options=None,
            cancel_event=self.cancel_event
        )
        if self.cancel_event.is_set():
            return
        if "error" in res:
            self.outq.put(("error", res))
        else:
            self.outq.put(("move", res))
