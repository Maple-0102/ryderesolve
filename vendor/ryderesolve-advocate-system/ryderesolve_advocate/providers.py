import json
import os
import re
import urllib.request
import urllib.error
from dataclasses import dataclass


class ProviderError(RuntimeError):
    pass


class CallableProvider:
    """Adapter for teammate's model call: fn(system_text, user_text) -> str or dict."""
    def __init__(self, fn):
        self.fn = fn

    def generate(self, system, user):
        return self.fn(system, user)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@dataclass
class GeminiProvider:
    api_key: str
    model: str
    timeout: float = 45

    @classmethod
    def from_env(cls):
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        model = os.environ.get("GEMINI_MODEL", "").strip()
        if not key or not model:
            raise ProviderError("Set GEMINI_API_KEY and GEMINI_MODEL in the backend environment")
        return cls(key, model)

    def generate(self, system, user):
        model = self.model.removeprefix("models/")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
            raise ProviderError("Invalid Gemini model identifier")
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json"}}
        request = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST")
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Gemini HTTP {exc.code}; check model, quota and credentials") from None
        except (OSError, ValueError):
            raise ProviderError("Gemini transport/response failure; credentials and response body omitted") from None
        candidates = payload.get("candidates", [])
        if not candidates or candidates[0].get("finishReason") != "STOP":
            raise ProviderError("Gemini returned blocked, incomplete or missing candidate")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            raise ProviderError("Gemini returned no usable JSON text")
        return text
