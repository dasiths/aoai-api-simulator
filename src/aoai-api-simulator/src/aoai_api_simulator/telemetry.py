import logging
import os

# from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log_level = os.getenv("LOG_LEVEL") or "INFO"

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)
logging.getLogger("azure").setLevel(logging.WARNING)

opentelemetry_exporter_otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
application_insights_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")


def setup_telemetry() -> bool:
    using_azure_monitor: bool

    if application_insights_connection_string:
        logger.info("🚀 Configuring Azure Monitor telemetry")

        # Options: https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/monitor/azure-monitor-opentelemetry#usage
        configure_azure_monitor(connection_string=application_insights_connection_string)
        using_azure_monitor = True
    else:
        using_azure_monitor = False
        logger.info("Azure Monitor telemetry not configured (set APPLICATIONINSIGHTS_CONNECTION_STRING)")

    if opentelemetry_exporter_otlp_endpoint:
        logger.info("🚀 Configuring OTLP telemetry")

        # setup the instrumentors
        resource = Resource(attributes={"service.name": os.getenv("OTEL_SERVICE_NAME", "aoai-api-simulator")})

        # tracing
        if not using_azure_monitor:
            trace.set_tracer_provider(TracerProvider(resource=resource))

        span_processor = BatchSpanProcessor(OTLPSpanExporter())
        trace.get_tracer_provider().add_span_processor(span_processor)

        # metrics
        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())

        if not using_azure_monitor:
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)
        else:
            meter_provider = metrics.get_meter_provider()
            # meter_provider.add_metric_reader() is not implemented in python sdk yet.
            # adding it manually
            meter_provider._all_metric_readers.add(metric_reader)
            metric_reader._set_collect_callback(meter_provider._measurement_consumer.collect)

        # logging
        logger_provider = LoggerProvider(
            resource=resource,
        )

        batch_log_record_processor = BatchLogRecordProcessor(OTLPLogExporter())
        logger_provider.add_log_record_processor(batch_log_record_processor)

        handler = LoggingHandler(level=os.getenv("OTEL_LOG_LEVEL", "INFO"), logger_provider=logger_provider)
        # Attach OTLP handler to root logger
        logging.getLogger().addHandler(handler)
    else:
        logger.info("🚀 OTLP telemetry exporter not configured (set OTEL_EXPORTER_OTLP_ENDPOINT)")

    return using_azure_monitor


def setup_auto_instrumentation(app: FastAPI, using_azure_monitor: bool):
    if not using_azure_monitor:
        RequestsInstrumentor().instrument()
        FastAPIInstrumentor.instrument_app(app)
    else:
        logger.info("Skipping instrumenting libraries as they are done by the Azure OTEL Distro already.")
