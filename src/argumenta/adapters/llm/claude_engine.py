import time
from typing import Any

import anthropic
from anthropic.types import ToolChoiceToolParam, ToolParam
from pydantic import BaseModel, Field, ValidationError

from argumenta.adapters.llm.contract import Effort, ensure_usable
from argumenta.adapters.llm.prompts.evaluation_v1 import (
    FULL_ESSAY_RULE,
    PROMPT_VERSION,
    SCENE_TEXT_RULE,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
from argumenta.application.evaluation.ports import EngineRequest, EngineResult
from argumenta.domain.enums import AnnotationType, Dimension, Severity
from argumenta.domain.errors import EvaluationFailedError
from argumenta.domain.evaluation import Annotation, DimensionScore


class ScoreOutput(BaseModel):
    """Typed output contract of the engine (acceptance criterion of issue #7)."""

    dimension: Dimension
    score: int = Field(ge=0, le=100)
    evidence: str = Field(min_length=1)


class AnnotationOutput(BaseModel):
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=1)
    type: AnnotationType
    severity: Severity
    message: str = Field(min_length=1)
    suggestion: str | None = None
    priority: int = Field(ge=1, le=9)


class EvaluationOutput(BaseModel):
    scores: list[ScoreOutput]
    annotations: list[AnnotationOutput]


_TOOL_NAME = "report_evaluation"


def _tool_definition() -> ToolParam:
    return ToolParam(
        name=_TOOL_NAME,
        description="Report the structured evaluation of the student's text.",
        input_schema=EvaluationOutput.model_json_schema(),
    )


def parse_engine_output(payload: dict[str, Any], text: str) -> EvaluationOutput:
    """Validate the tool payload: pydantic contract and spans inside the text.
    Which dimensions were required is checked once, in the use case, so every
    engine is held to it. Raises EvaluationFailedError."""
    try:
        output = EvaluationOutput.model_validate(payload)
    except ValidationError as error:
        raise EvaluationFailedError(f"engine output rejected: {error}") from error

    for annotation in output.annotations:
        if annotation.span_end <= annotation.span_start or annotation.span_end > len(text):
            raise EvaluationFailedError(
                f"annotation span [{annotation.span_start}, {annotation.span_end}) "
                f"outside the text (len={len(text)})"
            )
    return output


def _format_anchors(request: EngineRequest) -> str:
    if not request.spelling_anchors:
        return "(nenhuma)"
    return "\n".join(
        f'- "{anchor.word}" em [{anchor.span_start}, {anchor.span_end})'
        for anchor in request.spelling_anchors
    )


def _format_dimensions(required: tuple[Dimension, ...]) -> str:
    return "\n".join(f"- {dimension.value}" for dimension in required)


class ClaudeEvaluationEngine:
    """Claude with forced tool use: the tool schema is what makes the output
    structured. Sonnet 5 rejects a non-default temperature and thinks
    adaptively, so repeatability comes from the forced contract and the
    versioned prompt, never from sampling parameters.

    `effort` defaults to the API default, so this adapter does not quietly
    change how hard the grader thinks. Lowering it is a decision to take with
    the calibration suite in hand, not in passing.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 8000,
        effort: Effort = "high",
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    def evaluate(self, request: EngineRequest) -> EngineResult:
        started = time.monotonic()
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                output_config={"effort": self._effort},
                system=SYSTEM_PROMPT,
                tools=[_tool_definition()],
                tool_choice=ToolChoiceToolParam(type="tool", name=_TOOL_NAME),
                messages=[
                    {
                        "role": "user",
                        "content": USER_TEMPLATE.format(
                            chapter_objective=request.chapter_objective,
                            evaluator_brief=request.evaluator_brief,
                            persona_brief=request.persona_brief,
                            min_words=request.min_words,
                            max_words=request.max_words,
                            anchors=_format_anchors(request),
                            dimensions=_format_dimensions(request.required_dimensions),
                            format_rule=FULL_ESSAY_RULE if request.full_essay else SCENE_TEXT_RULE,
                            text=request.text,
                        ),
                    }
                ],
            )
        except anthropic.AnthropicError as error:
            raise EvaluationFailedError(str(error)) from error
        latency_ms = int((time.monotonic() - started) * 1000)
        ensure_usable(response.stop_reason, self._max_tokens)

        payload = next(
            (block.input for block in response.content if block.type == "tool_use"), None
        )
        if not isinstance(payload, dict):
            raise EvaluationFailedError("engine returned no tool_use block")
        output = parse_engine_output(payload, request.text)

        return EngineResult(
            scores=tuple(
                DimensionScore(dimension=s.dimension, score=s.score, evidence=s.evidence)
                for s in output.scores
            ),
            annotations=tuple(
                Annotation(
                    span_start=a.span_start,
                    span_end=a.span_end,
                    type=a.type,
                    severity=a.severity,
                    message=a.message,
                    suggestion=a.suggestion,
                    priority=a.priority,
                )
                for a in output.annotations
            ),
            model=self._model,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
