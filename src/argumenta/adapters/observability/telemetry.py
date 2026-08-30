"""OTLP wiring (issue #51). One setting is the whole gate: no endpoint means no
provider, and the OTel API already falls back to a no-op tracer/meter on its
own, so nothing here can change behavior in dev or in tests."""

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from argumenta.settings import Settings

_httpx_instrumented = False


def build_tracer_provider(settings: Settings) -> TracerProvider | None:
    if not settings.otel_exporter_otlp_endpoint:
        return None
    resource = Resource.create({"service.name": settings.app_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    return provider


def build_meter_provider(settings: Settings) -> MeterProvider | None:
    if not settings.otel_exporter_otlp_endpoint:
        return None
    resource = Resource.create({"service.name": settings.app_name})
    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    return MeterProvider(resource=resource, metric_readers=[reader])


def configure_telemetry(settings: Settings) -> None:
    """Called once per process at startup; safe to call again (httpx is
    instrumented at most once, and a real provider, once set, cannot be
    replaced anyway, which is fine: only the first app instance needs it)."""
    global _httpx_instrumented
    if not _httpx_instrumented:
        HTTPXClientInstrumentor().instrument()
        _httpx_instrumented = True

    tracer_provider = build_tracer_provider(settings)
    if tracer_provider is not None:
        trace.set_tracer_provider(tracer_provider)

    meter_provider = build_meter_provider(settings)
    if meter_provider is not None:
        metrics.set_meter_provider(meter_provider)
