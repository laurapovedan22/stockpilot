import json

from stockpilot.config import settings
from stockpilot.domain.assistant.provider import OpenAIProvider


def test_optional_provider_tool_budget_without_external_calls(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-only")
    monkeypatch.setattr(settings, "openai_model", "test-model")
    payloads = []
    executed = []
    responses = [
        {
            "output": [
                {
                    "type": "function_call",
                    "name": "get_product",
                    "call_id": str(i),
                    "arguments": json.dumps({"identifier": "DEMO-004", "query": None}),
                }
                for i in range(5)
            ]
        },
        {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Verified explanation"}],
                }
            ]
        },
    ]

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return responses.pop(0)

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            payloads.append(kwargs["json"])
            return Response()

    monkeypatch.setattr("stockpilot.domain.assistant.provider.httpx.Client", Client)

    def execute(name, arguments):
        executed.append(name)
        return {"product": {"sku": arguments["identifier"]}}

    text = OpenAIProvider().explain("Explain", "Initial verified facts", execute, remaining_calls=3)
    assert text == "Verified explanation"
    assert len(executed) == 3  # plus initial offline read = maximum four per message
    assert payloads[-1]["tool_choice"] == "none"
    assert not payloads[0]["store"]
