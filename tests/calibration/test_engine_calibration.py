"""Issue #12: the calibration run itself, against the real engine.

Marked `calibration` and excluded by default (see pyproject addopts), because it
costs tokens and needs ARGUMENTA_ANTHROPIC_API_KEY. It runs on demand, when a
prompt changes, or weekly, never blocking a normal PR.
"""

import os
import pathlib

import pytest

from argumenta.adapters.llm.factory import vendor_api_key
from argumenta.adapters.llm.prompts.evaluation_v1 import PROMPT_VERSION
from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.application.evaluation.ports import EngineRequest, EvaluationEngine
from argumenta.domain.errors import EvaluationFailedError
from argumenta.domain.evaluation import ensure_graded_exactly
from argumenta.domain.lenses import GradingSpec, grading_spec
from argumenta.presentation.fastapi.dependencies import get_evaluation_engine
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
def engine() -> EvaluationEngine:
    """The engine production gets, from the same factory: measuring a hand built
    one would let the two drift apart silently."""
    settings = get_settings()
    if not vendor_api_key(settings, settings.llm_vendor):
        pytest.skip(f"set the API key of {settings.llm_vendor} to run the calibration suite")
    return get_evaluation_engine()


def test_the_engine_stays_within_tolerance_on_every_fixture(engine: EvaluationEngine) -> None:
    checker = SpyllsSpellChecker()
    settings = get_settings()
    outcomes: list[FixtureOutcome] = []
    input_tokens = output_tokens = 0
    try:
        for fixture in load_fixtures():
            spec = grading_spec(fixture.chapter_kind, fixture.exam)
            try:
                result = engine.evaluate(_request(fixture, spec, checker))
                ensure_graded_exactly(result.scores, spec.dimensions)
            except EvaluationFailedError as error:
                outcomes.append(failed(fixture, str(error)))
                continue
            input_tokens += result.input_tokens or 0
            output_tokens += result.output_tokens or 0
            outcomes.append(
                compare(fixture, {score.dimension: score.score for score in result.scores})
            )
    finally:
        run = CalibrationResult(
            prompt_version=PROMPT_VERSION,
            model=settings.evaluation_model,
            effort=settings.evaluation_effort,
            outcomes=tuple(outcomes),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        _publish(build_report(run))

    verdict = judge(run)
    assert verdict.passed, verdict.summary


def _request(
    fixture: CalibrationFixture, spec: GradingSpec, checker: SpyllsSpellChecker
) -> EngineRequest:
    """Exactly what the use case sends in production, minus the budget gate:
    deterministic anchors first, and the dimensions the chapter and the exam
    require (never re-derived here)."""
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


def _publish(report: str) -> None:
    """Into the job summary when running in Actions, and to stdout otherwise
    (the workflow runs pytest with -s so a passing run still shows it)."""
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with pathlib.Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(report + "\n")
