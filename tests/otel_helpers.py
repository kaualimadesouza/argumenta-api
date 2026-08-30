"""Shared narrowing for OTel's `InMemoryMetricReader` output: the SDK types data
points as a union across counters and histograms, so every test needs the same
`isinstance` narrowing to reach `.value`/`.sum`/`.attributes` under mypy strict."""

from opentelemetry.sdk.metrics.export import HistogramDataPoint, MetricsData, NumberDataPoint


def counter_points(data: MetricsData | None, metric_name: str) -> list[NumberDataPoint]:
    assert data is not None
    points: list[NumberDataPoint] = []
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name != metric_name:
                    continue
                for point in metric.data.data_points:
                    assert isinstance(point, NumberDataPoint)
                    points.append(point)
    return points


def histogram_points(data: MetricsData | None, metric_name: str) -> list[HistogramDataPoint]:
    assert data is not None
    points: list[HistogramDataPoint] = []
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name != metric_name:
                    continue
                for point in metric.data.data_points:
                    assert isinstance(point, HistogramDataPoint)
                    points.append(point)
    return points


def point_attributes(point: NumberDataPoint | HistogramDataPoint) -> dict[str, object]:
    assert point.attributes is not None
    return dict(point.attributes)
