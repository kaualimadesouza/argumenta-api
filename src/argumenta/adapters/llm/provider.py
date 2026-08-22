"""One call contract for every model vendor: the engines say what they need
(system, user, how much room, how much thinking) and a provider knows how to ask
for it. Swapping Claude for GPT or Gemini is configuration, not a new engine."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from argumenta.adapters.llm.effort import Effort

Vendor = Literal["anthropic", "openai", "google"]


@dataclass(frozen=True)
class LlmCall:
    system: str
    user: str
    max_tokens: int
    effort: Effort | None = None
    """None asks for the vendor default; not every model accepts the knob."""


@dataclass(frozen=True)
class StructuredCall(LlmCall):
    """A call whose answer must match a JSON Schema. Each vendor enforces it its
    own way (forced tool use, strict structured output, response schema)."""

    name: str = "report"
    description: str = ""
    schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class LlmUsage:
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class StructuredReply:
    payload: dict[str, Any]
    model: str
    usage: LlmUsage


@dataclass(frozen=True)
class TextReply:
    body: str
    model: str
    usage: LlmUsage


class LlmProvider(Protocol):
    @property
    def model(self) -> str: ...

    def structured(self, call: StructuredCall) -> StructuredReply:
        """The payload validated against the schema, or EvaluationFailedError."""
        ...

    def text(self, call: LlmCall) -> TextReply: ...
