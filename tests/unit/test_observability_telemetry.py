"""Issue #51: OTLP is vendor-neutral, gated by one setting. The builders are
pure (never touch the global SDK registry), so tests never leak state across
the suite the way `trace.set_tracer_provider` would (it cannot be undone)."""

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from argumenta.adapters.observability.telemetry import (
    build_meter_provider,
    build_tracer_provider,
)
from argumenta.settings import Settings


class TestBuildTracerProvider:
    def test_without_an_endpoint_nothing_is_built(self) -> None:
        assert build_tracer_provider(Settings()) is None

    def test_with_an_endpoint_a_provider_is_built(self) -> None:
        provider = build_tracer_provider(
            Settings(otel_exporter_otlp_endpoint="http://localhost:4318")
        )

        assert isinstance(provider, TracerProvider)
        assert provider.resource.attributes["service.name"] == "argumenta-api"


class TestBuildMeterProvider:
    def test_without_an_endpoint_nothing_is_built(self) -> None:
        assert build_meter_provider(Settings()) is None

    def test_with_an_endpoint_a_provider_is_built(self) -> None:
        provider = build_meter_provider(
            Settings(otel_exporter_otlp_endpoint="http://localhost:4318")
        )

        assert isinstance(provider, MeterProvider)
        assert provider._sdk_config.resource.attributes["service.name"] == "argumenta-api"


def test_without_the_env_var_the_app_boots_and_nothing_is_exported() -> None:
    """Issue #51 acceptance criterion, proven the direct way: the default
    Settings has no endpoint, and every integration test already boots
    `create_app()` and calls a real route on top of that default."""
    assert Settings().otel_exporter_otlp_endpoint is None
