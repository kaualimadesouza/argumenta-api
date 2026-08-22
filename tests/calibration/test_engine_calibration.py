"""Issue #12: the calibration run itself, against the real engine.

Marked `calibration` and excluded by default (see pyproject addopts), because
it costs tokens and needs ARGUMENTA_ANTHROPIC_API_KEY. It runs on demand or on
a schedule, never blocking a normal PR.
"""

import os
import pathlib

import pytest

from argumenta.adapters.llm.claude_engine import ClaudeEvaluationEngine
from argumenta.adapters.llm.prompts.evaluation_v1 import PROMPT_VERSION
from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.application.evaluation.ports import EngineRequest, EngineResult
from argumenta.domain.enums import Dimension
from argumenta.domain.errors import EvaluationFailedError
from argumenta.domain.lenses import grading_spec
from argumenta.settings import get_settings
from tests.calibration.harness import (
    CalibrationFixture,
    CalibrationResult,
    FixtureOutcome,
    build_report,
    compare,
    failed,
    judge,
    load_fixtures,
)

pytestmark = pytest.mark.calibration


@pytest.fixture(scope="module")
def engine() -> ClaudeEvaluationEngine:
    settings = get_settings()
    if not settings.anthropic_api_key:
        pytest.skip("set ARGUMENTA_ANTHROPIC_API_KEY to run the calibration suite")
    return ClaudeEvaluationEngine(
        api_key=settings.anthropic_api_key, model=settings.evaluation_model
    )


def test_the_engine_stays_within_tolerance_on_every_fixture(
    engine: ClaudeEvaluationEngine,
) -> None:
    checker = SpyllsSpellChecker()
    outcomes: list[FixtureOutcome] = []
    input_tokens = output_tokens = 0
    try:
        for fixture in load_fixtures():
            try:
                result = engine.evaluate(_request(fixture, checker))
            except EvaluationFailedError as error:
                outcomes.append(failed(fixture, str(error)))
                continue
            input_tokens += result.input_tokens or 0
            output_tokens += result.output_tokens or 0
            outcomes.append(compare(fixture, _scores(result)))
    finally:
        run = CalibrationResult(
            prompt_version=PROMPT_VERSION,
            model=get_settings().evaluation_model,
            outcomes=tuple(outcomes),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        report = build_report(run)
        _publish(report)

    verdict = judge(run)
    assert verdict.passed, f"{verdict.summary}\n\n{report}"


def _request(fixture: CalibrationFixture, checker: SpyllsSpellChecker) -> EngineRequest:
    """Exactly what the use case sends in production: the deterministic anchors
    first, and the dimensions the chapter and the exam require."""
    spec = grading_spec(fixture.chapter_kind, fixture.exam)
    return EngineRequest(
        text=fixture.text,
        chapter_objective=fixture.chapter_objective,
        evaluator_brief=fixture.evaluator_brief,
        persona_brief=fixture.persona_brief,
        min_words=fixture.min_words,
        max_words=fixture.max_words,
        spelling_anchors=checker.find_unknown_words(fixture.text),
        required_dimensions=spec.dimensions,
        full_essay=spec.full_essay,
    )


def _scores(result: EngineResult) -> dict[Dimension, int]:
    return {score.dimension: score.score for score in result.scores}


def _publish(report: str) -> None:
    """Into the job summary when running in Actions, and to stdout otherwise
    (the workflow runs pytest with -s so a passing run still shows it)."""
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with pathlib.Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(report + "\n")
