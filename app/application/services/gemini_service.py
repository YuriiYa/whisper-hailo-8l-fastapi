import json
from urllib import error, request


class GeminiService:
    RESPONSE_LENGTH_SYSTEM_PROMPT = (
        "You are a concise assistant, aswering very laconically. Respond in 2 to 5 complete sentences. "
        "Do not use bullet points unless explicitly requested."
    )

    def __init__(self, api_key: str, model: str, timeout_seconds: int = 30):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.timeout_seconds = timeout_seconds

    def ask(self, question: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        if not self.model:
            raise RuntimeError("GEMINI_MODEL is not configured")

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )

        payload = {
            "system_instruction": {
                "parts": [
                    {
                        "text": self.RESPONSE_LENGTH_SYSTEM_PROMPT,
                    }
                ]
            },
            "contents": [
                {
                    "parts": [
                        {"text": question},
                    ]
                }
            ]
        }

        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            details = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini HTTP error {e.code}: {details}") from e
        except error.URLError as e:
            raise RuntimeError(f"Gemini network error: {e.reason}") from e

        try:
            return body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError("Gemini response format is invalid") from e
