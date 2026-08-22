"""Gemini. The schema goes in the request as `response_schema`, inlined because
that dialect has no `$ref`, and thinking is a token budget instead of a level."""

import json
from typing import Any

from argumenta.adapters.llm.effort import GOOGLE_THINKING_BUDGET
from argumenta.adapters.llm.provider import (
    LlmCall,
    LlmUsage,
    StructuredCall,
    StructuredReply,
    TextReply,
)
from argumenta.adapters.llm.schema import inlined_schema
from argumenta.domain.errors import EvaluationFailedError

_UNUSABLE = ("MAX_TOKENS", "SAFETY", "RECITATION", "PROHIBITED_CONTENT")


class GoogleProvider:
    def __init__(
        self, api_key: str, model: str, timeout: float = 90.0, max_retries: int = 1
    ) -> None:
        # imported here: the SDK is an optional extra (see OpenAiProvider)
        from google import genai

        self._client = genai.Client(
            api_key=api_key,
            http_options={
                "timeout": int(timeout * 1000),
                "retry_options": {"attempts": max_retries + 1},
            },
        )
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def _generate(self, call: LlmCall, schema: dict[str, Any] | None = None) -> Any:
        from google.genai.types import GenerateContentConfigDict

        config: GenerateContentConfigDict = {
            "system_instruction": call.system,
            "max_output_tokens": call.max_tokens,
        }
        if schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = inlined_schema(schema)
        if call.effort is not None:
            config["thinking_config"] = {"thinking_budget": GOOGLE_THINKING_BUDGET[call.effort]}
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=call.user, config=config
            )
        except Exception as error:  # the SDK raises its own APIError hierarchy
            raise EvaluationFailedError(str(error)) from error
        reason = (
            getattr(response.candidates[0], "finish_reason", None) if response.candidates else None
        )
        if reason is not None and str(getattr(reason, "name", reason)) in _UNUSABLE:
            raise EvaluationFailedError(
                f"engine response unusable: stopped on {reason} with "
                f"max_output_tokens={call.max_tokens}"
            )
        return response

    def _usage(self, response: Any) -> LlmUsage:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return LlmUsage(input_tokens=None, output_tokens=None)
        return LlmUsage(
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
        )

    def structured(self, call: StructuredCall) -> StructuredReply:
        if call.schema is None:
            raise EvaluationFailedError("structured call without a schema")
        response = self._generate(call, schema=call.schema)
        try:
            payload = json.loads((response.text or "").strip())
        except json.JSONDecodeError as error:
            raise EvaluationFailedError(f"engine returned invalid JSON: {error}") from error
        if not isinstance(payload, dict):
            raise EvaluationFailedError("engine returned JSON that is not an object")
        return StructuredReply(payload=payload, model=self._model, usage=self._usage(response))

    def text(self, call: LlmCall) -> TextReply:
        response = self._generate(call)
        body = (response.text or "").strip()
        if not body:
            raise EvaluationFailedError("engine returned no text")
        return TextReply(body=body, model=self._model, usage=self._usage(response))
