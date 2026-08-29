"""Claude. Structured output comes from forced tool use; the sampling knobs are
gone in Sonnet 5, so repeatability rests on that contract plus the prompt."""

import anthropic
from anthropic import omit
from anthropic.types import (
    Message,
    MessageParam,
    OutputConfigParam,
    ToolChoiceToolParam,
    ToolParam,
)

from argumenta.adapters.llm.contract import ensure_usable
from argumenta.adapters.llm.provider import (
    LlmCall,
    LlmUsage,
    StructuredCall,
    StructuredReply,
    TextReply,
)
from argumenta.adapters.llm.schema import anthropic_strict_schema
from argumenta.adapters.llm.usage import billed_input_tokens
from argumenta.domain.errors import EvaluationFailedError


def _output_config(call: LlmCall) -> OutputConfigParam | anthropic.Omit:
    return omit if call.effort is None else OutputConfigParam(effort=call.effort)


def _usage(response: Message) -> LlmUsage:
    return LlmUsage(
        input_tokens=billed_input_tokens(response.usage),
        output_tokens=response.usage.output_tokens,
    )


class AnthropicProvider:
    def __init__(
        self, api_key: str, model: str, timeout: float = 90.0, max_retries: int = 1
    ) -> None:
        # one retry, because a timed out call is billed server side and the
        # retry is billed again without either being recorded
        self._client = anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def _messages(self, call: LlmCall) -> list[MessageParam]:
        return [MessageParam(role="user", content=call.user)]

    def structured(self, call: StructuredCall) -> StructuredReply:
        if call.schema is None:
            raise EvaluationFailedError("structured call without a schema")
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=call.max_tokens,
                output_config=_output_config(call),
                system=call.system,
                messages=self._messages(call),
                tools=[
                    # strict guarantees the payload validates: without it Sonnet
                    # occasionally drops a required field (seen live: severity)
                    ToolParam(
                        name=call.name,
                        description=call.description,
                        input_schema=anthropic_strict_schema(call.schema),
                        strict=True,
                    )
                ],
                tool_choice=ToolChoiceToolParam(type="tool", name=call.name),
            )
        except anthropic.AnthropicError as error:
            raise EvaluationFailedError(str(error)) from error
        ensure_usable(response.stop_reason, call.max_tokens)

        payload = next(
            (block.input for block in response.content if block.type == "tool_use"), None
        )
        if not isinstance(payload, dict):
            raise EvaluationFailedError("engine returned no tool_use block")
        return StructuredReply(payload=payload, model=self._model, usage=_usage(response))

    def text(self, call: LlmCall) -> TextReply:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=call.max_tokens,
                output_config=_output_config(call),
                system=call.system,
                messages=self._messages(call),
            )
        except anthropic.AnthropicError as error:
            raise EvaluationFailedError(str(error)) from error
        ensure_usable(response.stop_reason, call.max_tokens)

        body = "".join(block.text for block in response.content if block.type == "text").strip()
        if not body:
            raise EvaluationFailedError("engine returned no text")
        return TextReply(body=body, model=self._model, usage=_usage(response))
