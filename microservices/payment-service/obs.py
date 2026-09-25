import os
import logging
from logging_loki import LokiHandler
from pythonjsonlogger import jsonlogger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator

def setup_observability(app, service_name: str):
    # 1. Logging Setup
    loki_url = os.getenv('LOKI_URL', 'http://loki:3100/loki/api/v1/push')
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    
    # JSON Formatter
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    
    # Console Handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    # Loki Handler
    loki_handler = LokiHandler(url=loki_url, tags={'application': service_name}, version='1')
    loki_handler.setFormatter(formatter)
    logger.addHandler(loki_handler)

    # 2. OpenTelemetry Tracing Setup
    otlp_endpoint = os.getenv('OTLP_ENDPOINT', 'http://jaeger:4317')
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Instrument HTTPX
    HTTPXClientInstrumentor().instrument()

    # 3. Prometheus Metrics Setup
    Instrumentator().instrument(app).expose(app)
    
    return logger
