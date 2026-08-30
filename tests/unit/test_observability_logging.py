"""Issue #51: one JSON object per log line, correlated to the request and to
whatever trace is active, replacing the ad hoc logging in the entrypoints."""

import json
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from argumenta.adapters.observability.logging import JsonFormatter, request_id_var


def _log(logger: logging.Logger, level: int, message: str) -> str:
    """One record through the formatter, captured via a private handler."""
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(self.format(record))

    handler = _Capture()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    try:
        logger.log(level, message)
    finally:
        logger.removeHandler(handler)
    return captured[0]


class TestJsonFormatter:
    def test_the_line_is_valid_json_with_the_message_and_level(self) -> None:
        logger = logging.getLogger("test.plain")
        logger.setLevel(logging.INFO)

        line = _log(logger, logging.WARNING, "budget at 80%")
        payload = json.loads(line)

        assert payload["message"] == "budget at 80%"
        assert payload["level"] == "WARNING"
        assert payload["logger"] == "test.plain"

    def test_no_request_id_means_none_not_a_missing_key(self) -> None:
        logger = logging.getLogger("test.no_request")
        logger.setLevel(logging.INFO)
        token = request_id_var.set(None)
        try:
            payload = json.loads(_log(logger, logging.INFO, "hi"))
        finally:
            request_id_var.reset(token)

        assert payload["request_id"] is None

    def test_the_active_request_id_is_carried(self) -> None:
        logger = logging.getLogger("test.request_id")
        logger.setLevel(logging.INFO)
        token = request_id_var.set("req-123")
        try:
            payload = json.loads(_log(logger, logging.INFO, "hi"))
        finally:
            request_id_var.reset(token)

        assert payload["request_id"] == "req-123"

    def test_a_line_logged_inside_a_span_carries_its_trace_and_span_id(self) -> None:
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        logger = logging.getLogger("test.trace")
        logger.setLevel(logging.INFO)

        with tracer.start_as_current_span("unit-test-span"):
            span_context = trace.get_current_span().get_span_context()
            payload = json.loads(_log(logger, logging.INFO, "hi"))

        assert payload["trace_id"] == format(span_context.trace_id, "032x")
        assert payload["span_id"] == format(span_context.span_id, "016x")

    def test_a_line_logged_outside_any_span_has_no_trace_fields(self) -> None:
        logger = logging.getLogger("test.no_trace")
        logger.setLevel(logging.INFO)

        payload = json.loads(_log(logger, logging.INFO, "hi"))

        assert "trace_id" not in payload
        assert "span_id" not in payload
