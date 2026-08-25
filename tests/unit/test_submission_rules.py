"""Unit tests of the pure submission rules (domain/submission.py)."""

import pytest

from argumenta.domain.enums import ChapterStatus, SubmissionContext, Verdict
from argumenta.domain.errors import ChapterNotWritableError
from argumenta.domain.submission import (
    count_words,
    next_status_for,
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


def test_count_words_splits_on_whitespace() -> None:
    assert count_words("a  escola\nprecisa   do festival") == 5
