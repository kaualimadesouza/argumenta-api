"""Every OTel metric instrument the app records, defined once (issue #51): two
counters built with the same name in different modules would be indistinguishable
on a dashboard until their unit or description quietly drifted apart."""

from opentelemetry import metrics

_meter = metrics.get_meter(__name__)

tokens_counter = _meter.create_counter(
    "argumenta.llm.tokens",
    unit="{token}",
    description="LLM tokens spent, by engine and direction",
)
evaluation_latency = _meter.create_histogram(
    "argumenta.evaluation.latency",
    unit="ms",
    description="Duration of the graded-correction LLM call",
)
submissions_counter = _meter.create_counter(
    "argumenta.submissions", description="Submissions graded, by verdict"
)
evaluation_failures = _meter.create_counter(
    "argumenta.evaluation.failures",
    description="5xx domain errors, by exception type",
)
budget_used_ratio = _meter.create_histogram(
    "argumenta.llm.budget_used_ratio",
    description="Fraction of the monthly LLM token budget spent, observed at each check",
)
