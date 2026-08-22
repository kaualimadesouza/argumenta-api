import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from argumenta.adapters.llm.effort import Effort
from argumenta.adapters.llm.prompts.evaluation_v1 import (
    FULL_ESSAY_RULE,
    PROMPT_VERSION,
    SCENE_TEXT_RULE,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
from argumenta.adapters.llm.prompts.student_text import defuse_fence
from argumenta.adapters.llm.provider import LlmProvider, StructuredCall
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
_TOOL_DESCRIPTION = "Report the structured evaluation of the student's text."


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


class LlmEvaluationEngine:
    """The graded correction, on whatever vendor the provider talks to. The
    structured contract and the versioned prompt are what make it repeatable;
    the model is configuration (issue #43)."""

    def __init__(
        self,
        provider: LlmProvider,
        max_tokens: int = 8000,
        effort: Effort | None = "high",
    ) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._effort = effort

    def evaluate(self, request: EngineRequest) -> EngineResult:
        started = time.monotonic()
        reply = self._provider.structured(
            StructuredCall(
                system=SYSTEM_PROMPT,
                user=USER_TEMPLATE.format(
                    chapter_objective=request.chapter_objective,
                    evaluator_brief=request.evaluator_brief,
                    persona_brief=request.persona_brief,
                    min_words=request.min_words,
                    max_words=request.max_words,
                    anchors=_format_anchors(request),
                    dimensions=_format_dimensions(request.required_dimensions),
                    format_rule=FULL_ESSAY_RULE if request.full_essay else SCENE_TEXT_RULE,
                    text=defuse_fence(request.text),
                ),
                max_tokens=self._max_tokens,
                effort=self._effort,
                name=_TOOL_NAME,
                description=_TOOL_DESCRIPTION,
                schema=EvaluationOutput.model_json_schema(),
            )
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        output = parse_engine_output(reply.payload, request.text)

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
            model=reply.model,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            input_tokens=reply.usage.input_tokens,
            output_tokens=reply.usage.output_tokens,
        )
