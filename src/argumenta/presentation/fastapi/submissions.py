import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from opentelemetry import metrics
from pydantic import BaseModel, Field

from argumenta.application.gameplay.ports import DraftRepository, ProgressWriter
from argumenta.application.gameplay.use_cases import (
    SaveDraftUseCase,
    SubmitArgument,
    SubmitArgumentUseCase,
)
from argumenta.domain.enums import (
    AnnotationType,
    ChapterStatus,
    Dimension,
    Exam,
    Severity,
    Verdict,
)
from argumenta.domain.lenses import ScaleSource
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_draft_repository,
    get_progress_writer,
    get_submit_argument_use_case,
)

router = APIRouter(prefix="/chapters", tags=["submissions"])

_meter = metrics.get_meter(__name__)
_submissions_counter = _meter.create_counter(
    "argumenta.submissions", description="Submissions graded, by verdict"
)

Progress = Annotated[ProgressWriter, Depends(get_progress_writer)]
Drafts = Annotated[DraftRepository, Depends(get_draft_repository)]
SubmitUseCase = Annotated[SubmitArgumentUseCase, Depends(get_submit_argument_use_case)]


class SubmissionRequest(BaseModel):
    body: str = Field(min_length=1)
    typing_ms: int | None = Field(default=None, ge=0)
    paste_count: int = Field(default=0, ge=0)


class ScoreResponse(BaseModel):
    dimension: Dimension
    score: int
    evidence: str
    passed_floor: bool


class AnnotationResponse(BaseModel):
    span_start: int
    span_end: int
    type: AnnotationType
    severity: Severity
    message: str
    suggestion: str | None
    priority: int


class LensCriterionResponse(BaseModel):
    code: str
    label: str
    score: int
    scale_max: int
    is_argumenta_extra: bool


class LensResponse(BaseModel):
    """The same internal correction in the scale of the student's exam."""

    exam: Exam
    version: str
    criteria: list[LensCriterionResponse]
    total: int | None
    total_max: int | None
    scale_source: ScaleSource
    """"board" is the exam board's own scale; "argumenta" is our aggregation and
    must not be rendered as an official grade."""


class SubmissionResponse(BaseModel):
    """Layered correction in one call: scoreboard, annotated spans, and the
    'para passar' priorities, plus where the chapter state machine landed."""

    submission_id: uuid.UUID
    attempt_number: int
    verdict: Verdict
    average_score: float
    floor_value: int
    min_average: int
    chapter_status: ChapterStatus
    scores: list[ScoreResponse]
    annotations: list[AnnotationResponse]
    para_passar: list[AnnotationResponse]
    lens: LensResponse


class DraftRequest(BaseModel):
    body: str


@router.post("/{chapter_id}/submissions", status_code=201)
def submit_argument(
    chapter_id: uuid.UUID,
    request: SubmissionRequest,
    user_id: CurrentUserId,
    use_case: SubmitUseCase,
) -> SubmissionResponse:
    result = use_case.execute(
        SubmitArgument(
            user_id=user_id,
            chapter_id=chapter_id,
            body=request.body,
            typing_ms=request.typing_ms,
            paste_count=request.paste_count,
        )
    )
    outcome = result.outcome
    _submissions_counter.add(1, {"verdict": outcome.verdict.value})
    annotations = [
        AnnotationResponse(
            span_start=a.span_start,
            span_end=a.span_end,
            type=a.type,
            severity=a.severity,
            message=a.message,
            suggestion=a.suggestion,
            priority=a.priority,
        )
        for a in outcome.annotations
    ]
    return SubmissionResponse(
        submission_id=result.submission_id,
        attempt_number=result.attempt_number,
        verdict=outcome.verdict,
        average_score=round(outcome.average_score, 2),
        floor_value=result.ruler.dimension_floor,
        min_average=result.ruler.min_average,
        chapter_status=result.chapter_status,
        scores=[
            ScoreResponse(
                dimension=s.dimension,
                score=s.score,
                evidence=s.evidence,
                passed_floor=s.passed_floor,
            )
            for s in outcome.scores
        ],
        annotations=annotations,
        para_passar=sorted((a for a in annotations if a.priority <= 3), key=lambda a: a.priority),
        lens=LensResponse(
            exam=result.lens.exam,
            version=result.lens.version,
            criteria=[
                LensCriterionResponse(
                    code=criterion.code,
                    label=criterion.label,
                    score=criterion.score,
                    scale_max=criterion.scale_max,
                    is_argumenta_extra=criterion.is_argumenta_extra,
                )
                for criterion in result.lens.criteria
            ],
            total=result.lens.total,
            total_max=result.lens.total_max,
            scale_source=result.lens.scale_source,
        ),
    )


@router.put("/{chapter_id}/draft", status_code=204)
def save_draft(
    chapter_id: uuid.UUID,
    request: DraftRequest,
    user_id: CurrentUserId,
    drafts: Drafts,
    progress: Progress,
) -> None:
    SaveDraftUseCase(drafts, progress).execute(user_id, chapter_id, request.body)
