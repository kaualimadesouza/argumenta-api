"""Issue #12: the calibration run itself, against the real engine.

Marked `calibration` and excluded by default (see pyproject addopts), because
it costs tokens and needs ARGUMENTA_ANTHROPIC_API_KEY. It runs as a manual or
nightly job, never blocking a normal PR.
"""

import os
import pathlib

import pytest

from argumenta.adapters.llm.claude_engine import ClaudeEvaluationEngine
from argumenta.adapters.llm.prompts.evaluation_v1 import PROMPT_VERSION
from argumenta.application.evaluation.ports import EngineRequest
from argumenta.domain.enums import Dimension
from argumenta.domain.evaluation import BASE_DIMENSIONS
from argumenta.settings import get_settings
from tests.calibration.harness import (
    CalibrationFixture,
    CalibrationResult,
    build_report,
    compare,
    load_fixtures,
)

pytestmark = pytest.mark.calibration


def _required(fixture: CalibrationFixture) -> tuple[Dimension, ...]:
    """The fixture's own reference decides what the engine is asked for, so a
    boss fixture exercises the intervention proposal too."""
    extra = tuple(d for d in fixture.expected if d not in BASE_DIMENSIONS)
    return (*BASE_DIMENSIONS, *extra)


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
    outcomes = []
    for fixture in load_fixtures():
        result = engine.evaluate(
            EngineRequest(
                text=fixture.text,
                chapter_objective=fixture.chapter_objective,
                evaluator_brief=fixture.evaluator_brief,
                persona_brief=fixture.persona_brief,
                min_words=fixture.min_words,
                max_words=fixture.max_words,
                spelling_anchors=(),
                required_dimensions=_required(fixture),
                full_essay=Dimension.PROPOSTA_INTERVENCAO in fixture.expected,
            )
        )
        actual = {score.dimension: score.score for score in result.scores}
        outcomes.append(compare(fixture, actual))

    report = build_report(
        CalibrationResult(prompt_version=PROMPT_VERSION, outcomes=tuple(outcomes))
    )
    _publish(report)
    failed = [outcome.fixture.slug for outcome in outcomes if not outcome.passed]
    assert not failed, f"drift beyond tolerance in: {', '.join(failed)}\n\n{report}"


def _publish(report: str) -> None:
    """Straight into the job summary when running in Actions, stdout otherwise."""
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with pathlib.Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(report + "\n")
