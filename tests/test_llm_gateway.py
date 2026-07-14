import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.llm_gateway import LLMGateway


class _FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self._body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._body.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


class TestLLMGateway(unittest.TestCase):
    def test_disabled_provider_does_not_send_network_request(self) -> None:
        with patch.dict("os.environ", {"LLM_PROVIDER": "disabled"}, clear=False):
            with patch("services.llm_gateway.urlopen") as urlopen:
                result = LLMGateway.from_environment().complete_json(
                    system_prompt="Return JSON.",
                    user_prompt="订单 ORD-1001 未收到",
                )

        self.assertFalse(result.success)
        self.assertEqual(result.provider, "disabled")
        self.assertEqual(result.fallback_reason, "LLM provider is disabled")
        urlopen.assert_not_called()

    def test_openai_compatible_provider_parses_content_and_usage(self) -> None:
        response_payload = {
            "choices": [{"message": {"content": '{"intent":"logistics_delay"}'}}],
            "usage": {"prompt_tokens": 18, "completion_tokens": 6},
        }
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai_compatible",
                "LLM_BASE_URL": "https://llm.example/v1",
                "LLM_API_KEY": "test-key",
                "LLM_MODEL": "test-model",
            },
            clear=False,
        ):
            with patch("services.llm_gateway.urlopen", return_value=_FakeHttpResponse(response_payload)) as urlopen:
                result = LLMGateway.from_environment().complete_json(
                    system_prompt="Return JSON.",
                    user_prompt="订单 ORD-1001 未收到",
                )

        self.assertTrue(result.success)
        self.assertEqual(result.content, {"intent": "logistics_delay"})
        self.assertEqual(result.provider, "openai_compatible")
        self.assertEqual(result.model, "test-model")
        self.assertEqual(result.input_tokens, 18)
        self.assertEqual(result.output_tokens, 6)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://llm.example/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    def test_invalid_model_json_returns_fallback_reason(self) -> None:
        response_payload = {"choices": [{"message": {"content": "不是 JSON"}}]}
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai_compatible",
                "LLM_BASE_URL": "https://llm.example/v1",
                "LLM_API_KEY": "test-key",
                "LLM_MODEL": "test-model",
            },
            clear=False,
        ):
            with patch("services.llm_gateway.urlopen", return_value=_FakeHttpResponse(response_payload)):
                result = LLMGateway.from_environment().complete_json(
                    system_prompt="Return JSON.",
                    user_prompt="订单 ORD-1001 未收到",
                )

        self.assertFalse(result.success)
        self.assertEqual(result.provider, "openai_compatible")
        self.assertIn("invalid JSON", result.fallback_reason or "")

    def test_invalid_base_url_returns_fallback_instead_of_raising(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai_compatible",
                "LLM_BASE_URL": "not-a-valid-url",
                "LLM_API_KEY": "test-key",
                "LLM_MODEL": "test-model",
            },
            clear=False,
        ):
            result = LLMGateway.from_environment().complete_json(
                system_prompt="Return JSON.",
                user_prompt="订单 ORD-1001 未收到",
            )

        self.assertFalse(result.success)
        self.assertIn("LLM request could not be created", result.fallback_reason or "")

    def test_ollama_provider_uses_chat_api_and_parses_token_counts(self) -> None:
        response_payload = {
            "message": {"content": '{"order_id":"ORD-1001"}'},
            "prompt_eval_count": 16,
            "eval_count": 4,
        }
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "ollama",
                "LLM_BASE_URL": "http://127.0.0.1:11434",
                "LLM_MODEL": "qwen3:8b",
            },
            clear=False,
        ):
            with patch("services.llm_gateway.urlopen", return_value=_FakeHttpResponse(response_payload)) as urlopen:
                result = LLMGateway.from_environment().complete_json(
                    system_prompt="Return JSON.",
                    user_prompt="订单 ORD-1001 未收到",
                )

        self.assertTrue(result.success)
        self.assertEqual(result.content, {"order_id": "ORD-1001"})
        self.assertEqual(result.input_tokens, 16)
        self.assertEqual(result.output_tokens, 4)
        self.assertEqual(urlopen.call_args.args[0].full_url, "http://127.0.0.1:11434/api/chat")
