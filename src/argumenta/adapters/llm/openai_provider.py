"""GPT. Structured output is a strict json_schema response format, and the
thinking knob only exists on the reasoning models, so it is sent when asked for."""

import json
from typing import Any

from argumenta.adapters.llm.effort import OPENAI_EFFORT
from argumenta.adapters.llm.provider import (
    LlmCall,
    LlmUsage,
    StructuredCall,
    StructuredReply,
    TextReply,
)
from argumenta.adapters.llm.schema import strict_schema
from argumenta.domain.errors import EvaluationFailedError

_TRUNCATED = ("length", "content_filter")


class OpenAiProvider:
    def __init__(
        self, api_key: str, model: str, timeout: float = 90.0, max_retries: int = 1
    ) -> None:
        # imported here: the SDK is an optional extra, so a deploy that only
        # talks to Claude does not carry it
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def _create(self, call: LlmCall, **extra: Any) -> Any:
        knobs: dict[str, Any] = (
            {} if call.effort is None else {"reasoning_effort": OPENAI_EFFORT[call.effort]}
        )
        try:
            return self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=call.max_tokens,
                messages=[
                    {"role": "system", "content": call.system},
                    {"role": "user", "content": call.user},
                ],
                **knobs,
                **extra,
            )
        except Exception as error:  # the SDK's errors all descend from its own base
            raise EvaluationFailedError(str(error)) from error

    def _body(self, response: Any, call: LlmCall) -> str:
        choice = response.choices[0]
        if choice.finish_reason in _TRUNCATED:
            raise EvaluationFailedError(
                f"engine response unusable: stopped on {choice.finish_reason} with "
                f"max_completion_tokens={call.max_tokens}"
            )
        if choice.message.refusal:
            raise EvaluationFailedError("engine refused to answer this request")
        return (choice.message.content or "").strip()

    def _usage(self, response: Any) -> LlmUsage:
        usage = response.usage
        if usage is None:
            return LlmUsage(input_tokens=None, output_tokens=None)
        return LlmUsage(input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens)

    def structured(self, call: StructuredCall) -> StructuredReply:
        if call.schema is None:
            raise EvaluationFailedError("structured call without a schema")
        response = self._create(
            call,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": call.name,
                    "schema": strict_schema(call.schema),
                    "strict": True,
                },
            },
        )
        body = self._body(response, call)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise EvaluationFailedError(f"engine returned invalid JSON: {error}") from error
        if not isinstance(payload, dict):
            raise EvaluationFailedError("engine returned JSON that is not an object")
        return StructuredReply(payload=payload, model=self._model, usage=self._usage(response))

    def text(self, call: LlmCall) -> TextReply:
        response = self._create(call)
        body = self._body(response, call)
        if not body:
            raise EvaluationFailedError("engine returned no text")
        return TextReply(body=body, model=self._model, usage=self._usage(response))
