import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from argumenta.application.gameplay.ports import DraftRepository, ProgressWriter
from argumenta.application.gameplay.use_cases import (
    CorrectionView,
    GetSubmissionHistoryUseCase,
    GetSubmissionUseCase,
    SaveDraftUseCase,
    SubmitArgument,
    SubmitArgumentUseCase,
)
from argumenta.application.track.ports import ContentRepository, ProgressRepository
from argumenta.domain.enums import (
    AnnotationType,
    ChapterStatus,
    Dimension,
    Exam,
    Severity,
    SubmissionStatus,
    Verdict,
)
from argumenta.domain.lenses import ScaleSource
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_content_repository,
    get_draft_repository,
    get_get_submission_history_use_case,
    get_get_submission_use_case,
    get_progress_repository,
    get_progress_writer,
    get_submit_argument_use_case,
)

router = APIRouter(prefix="/chapters", tags=["submissions"])
polling_router = APIRouter(prefix="/submissions", tags=["submissions"])

Progress = Annotated[ProgressWriter, Depends(get_progress_writer)]
Drafts = Annotated[DraftRepository, Depends(get_draft_repository)]
SubmitUseCase = Annotated[SubmitArgumentUseCase, Depends(get_submit_argument_use_case)]
GetUseCase = Annotated[GetSubmissionUseCase, Depends(get_get_submission_use_case)]
Content = Annotated[ContentRepository, Depends(get_content_repository)]
TrackProgress = Annotated[ProgressRepository, Depends(get_progress_repository)]
GetHistoryUseCase = Annotated[
    GetSubmissionHistoryUseCase, Depends(get_get_submission_history_use_case)
]


class SubmissionRequest(BaseModel):
    body: str = Field(min_length=1)
    typing_ms: int | None = Field(default=None, ge=0)
    paste_count: int = Field(default=0, ge=0)


class PendingSubmissionResponse(BaseModel):
    """The correction runs out of band (issue #68): poll GET /submissions/{id}
    until the status leaves "evaluating"."""

    submission_id: uuid.UUID
    attempt_number: int
    status: SubmissionStatus


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


class CorrectionResponse(BaseModel):
    """Layered correction: scoreboard, annotated spans, and the 'para passar'
    priorities, plus where the chapter state machine landed."""

    verdict: Verdict
    average_score: float
    floor_value: int
    min_average: int
    chapter_status: ChapterStatus
    scores: list[ScoreResponse]
    annotations: list[AnnotationResponse]
    para_passar: list[AnnotationResponse]
    lens: LensResponse


class SubmissionStateResponse(BaseModel):
    """One polling answer: result is present exactly when status is
    "evaluated"; "failed" is recoverable (the student may resubmit)."""

    submission_id: uuid.UUID
    chapter_id: uuid.UUID
    attempt_number: int
    status: SubmissionStatus
    result: CorrectionResponse | None


class PastSubmissionResponse(BaseModel):
    submission_id: uuid.UUID
    attempt_number: int
    body: str
    verdict: Verdict
    average_score: float
    floor_value: int
    min_average: int
    scores: list[ScoreResponse]
    lens: LensResponse
    created_at: datetime


class DraftRequest(BaseModel):
    body: str


@router.post("/{chapter_id}/submissions", status_code=202)
def submit_argument(
    chapter_id: uuid.UUID,
    request: SubmissionRequest,
    user_id: CurrentUserId,
    use_case: SubmitUseCase,
) -> PendingSubmissionResponse:
    pending = use_case.execute(
        SubmitArgument(
            user_id=user_id,
            chapter_id=chapter_id,
            body=request.body,
            typing_ms=request.typing_ms,
            paste_count=request.paste_count,
        )
    )
    return PendingSubmissionResponse(
        submission_id=pending.submission_id,
        attempt_number=pending.attempt_number,
        status=SubmissionStatus.EVALUATING,
    )


@polling_router.get("/{submission_id}")
def get_submission(
    submission_id: uuid.UUID,
    user_id: CurrentUserId,
    use_case: GetUseCase,
) -> SubmissionStateResponse:
    view = use_case.execute(user_id, submission_id)
    return SubmissionStateResponse(
        submission_id=view.submission_id,
        chapter_id=view.chapter_id,
        attempt_number=view.attempt_number,
        status=view.status,
        result=None if view.result is None else _correction_response(view.result),
    )


def _correction_response(view: CorrectionView) -> CorrectionResponse:
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
        for a in view.annotations
    ]
    return CorrectionResponse(
        verdict=view.verdict,
        average_score=round(view.average_score, 2),
        floor_value=view.floor_value,
        min_average=view.min_average,
        chapter_status=view.chapter_status,
        scores=[
            ScoreResponse(
                dimension=s.dimension,
                score=s.score,
                evidence=s.evidence,
                passed_floor=s.passed_floor,
            )
            for s in view.scores
        ],
        annotations=annotations,
        para_passar=sorted((a for a in annotations if a.priority <= 3), key=lambda a: a.priority),
        lens=LensResponse(
            exam=view.lens.exam,
            version=view.lens.version,
            criteria=[
                LensCriterionResponse(
                    code=criterion.code,
                    label=criterion.label,
                    score=criterion.score,
                    scale_max=criterion.scale_max,
                    is_argumenta_extra=criterion.is_argumenta_extra,
                )
                for criterion in view.lens.criteria
            ],
            total=view.lens.total,
            total_max=view.lens.total_max,
            scale_source=view.lens.scale_source,
        ),
    )


@router.get("/{chapter_id}/submissions")
def get_submission_history(
    chapter_id: uuid.UUID,
    user_id: CurrentUserId,
    use_case: GetHistoryUseCase,
) -> list[PastSubmissionResponse]:
    attempts = use_case.execute(user_id, chapter_id)
    return [
        PastSubmissionResponse(
            submission_id=a.submission_id,
            attempt_number=a.attempt_number,
            body=a.body,
            verdict=a.verdict,
            average_score=round(a.average_score, 2),
            floor_value=a.floor_value,
            min_average=a.min_average,
            scores=[
                ScoreResponse(
                    dimension=s.dimension,
                    score=s.score,
                    evidence=s.evidence,
                    passed_floor=s.passed_floor,
                )
                for s in a.scores
            ],
            lens=LensResponse(
                exam=a.lens.exam,
                version=a.lens.version,
                criteria=[
                    LensCriterionResponse(
                        code=c.code,
                        label=c.label,
                        score=c.score,
                        scale_max=c.scale_max,
                        is_argumenta_extra=c.is_argumenta_extra,
                    )
                    for c in a.lens.criteria
                ],
                total=a.lens.total,
                total_max=a.lens.total_max,
                scale_source=a.lens.scale_source,
            ),
            created_at=a.created_at.replace(tzinfo=UTC),
        )
        for a in attempts
    ]


@router.put("/{chapter_id}/draft", status_code=204)
def save_draft(
    chapter_id: uuid.UUID,
    request: DraftRequest,
    user_id: CurrentUserId,
    drafts: Drafts,
    progress: Progress,
) -> None:
    SaveDraftUseCase(drafts, progress).execute(user_id, chapter_id, request.body)
