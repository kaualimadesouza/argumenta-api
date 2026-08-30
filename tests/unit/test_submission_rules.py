"""Unit tests of the pure submission rules (domain/submission.py)."""

import pytest

from argumenta.domain.enums import ChapterStatus, SubmissionContext, Verdict
from argumenta.domain.errors import ChapterNotWritableError
from argumenta.domain.submission import (
    count_words,
    next_status_for,
    resolve_status_after_evaluation,
    submission_context_for,
)


class TestSubmissionContext:
    def test_available_and_drafting_write_in_the_main_flow(self) -> None:
        assert submission_context_for(ChapterStatus.AVAILABLE) == SubmissionContext.MAIN
        assert submission_context_for(ChapterStatus.DRAFTING) == SubmissionContext.MAIN

    def test_recovery_scene_writes_in_the_recovery_context(self) -> None:
        assert submission_context_for(ChapterStatus.IN_RECOVERY) == SubmissionContext.RECOVERY

    @pytest.mark.parametrize(
        "status",
        [ChapterStatus.LOCKED, ChapterStatus.PASSED, ChapterStatus.IN_CONSEQUENCE],
    )
    def test_non_writable_states_are_rejected(self, status: ChapterStatus) -> None:
        with pytest.raises(ChapterNotWritableError):
            submission_context_for(status)


class TestVerdictTransitions:
    def test_approved_passes_the_chapter(self) -> None:
        assert next_status_for(Verdict.APPROVED) == ChapterStatus.PASSED

    def test_technical_failure_keeps_the_student_drafting(self) -> None:
        assert next_status_for(Verdict.FAILED_TECHNICAL) == ChapterStatus.DRAFTING

    def test_persuasion_failure_opens_the_consequence(self) -> None:
        assert next_status_for(Verdict.FAILED_PERSUASION) == ChapterStatus.IN_CONSEQUENCE


class TestStatusAfterEvaluation:
    """With async evaluation two submissions can be in flight: a verdict that
    lands AFTER the chapter passed must never regress it."""

    @pytest.mark.parametrize(
        "verdict",
        [Verdict.APPROVED, Verdict.FAILED_TECHNICAL, Verdict.FAILED_PERSUASION],
    )
    def test_passed_is_final_whatever_the_late_verdict_says(self, verdict: Verdict) -> None:
        assert (
            resolve_status_after_evaluation(ChapterStatus.PASSED, verdict) == ChapterStatus.PASSED
        )

    @pytest.mark.parametrize(
        "current",
        [ChapterStatus.AVAILABLE, ChapterStatus.DRAFTING, ChapterStatus.IN_RECOVERY],
    )
    def test_otherwise_the_verdict_rules(self, current: ChapterStatus) -> None:
        for verdict in Verdict:
            assert resolve_status_after_evaluation(current, verdict) == next_status_for(verdict)


def test_count_words_splits_on_whitespace() -> None:
    assert count_words("a  escola\nprecisa   do festival") == 5
