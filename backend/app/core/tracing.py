"""OpenTelemetry tracing setup for Azure AI agent monitoring.

This module configures OpenTelemetry instrumentation following Azure AI Foundry
patterns for comprehensive agent observability with Application Insights.

Based on: https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/trace-agents-sdk
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer, Status, StatusCode

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[Tracer] = None
_tracer_provider: Optional[TracerProvider] = None


def setup_tracing(
    connection_string: Optional[str] = None,
    enable_content_recording: bool = True
) -> bool:
    """Set up OpenTelemetry tracing with Azure Monitor.
    
    Args:
        connection_string: Application Insights connection string
        enable_content_recording: Whether to capture request/response content
        
    Returns:
        True if tracing was successfully configured
    """
    global _tracer, _tracer_provider
    
    if _tracer is not None:
        logger.debug("Tracing already configured")
        return True
    
    try:
        from app.core.config import get_settings
        settings = get_settings()
        
        if not settings.enable_telemetry:
            logger.info("Telemetry disabled in configuration")
            return False
        
        # Enable content recording for detailed traces
        if enable_content_recording:
            os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
        
        # Use connection string from parameter or settings
        conn_str = connection_string or settings.application_insights_connection_string
        
        if conn_str:
            # Configure Azure Monitor with OpenTelemetry
            from azure.monitor.opentelemetry import configure_azure_monitor
            
            configure_azure_monitor(
                connection_string=conn_str,
                enable_live_metrics=True,
            )
            logger.info("✅ Azure Monitor tracing configured with Application Insights")
        else:
            logger.warning("⚠️ No Application Insights connection string found")
            # Still set up basic tracing without Azure Monitor
            _tracer_provider = TracerProvider()
            trace.set_tracer_provider(_tracer_provider)
        
        # Instrument OpenAI SDK
        try:
            from opentelemetry.instrumentation.openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument()
            logger.info("✅ OpenAI SDK instrumented for tracing")
        except ImportError:
            logger.warning("⚠️ OpenAI instrumentation not available")
        
        # Get tracer for custom spans
        _tracer = trace.get_tracer(__name__, "1.0.0")
        
        logger.info("✅ OpenTelemetry tracing configured successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to configure tracing: {e}")
        return False


def get_tracer() -> Optional[Tracer]:
    """Get the global tracer instance.
    
    Returns:
        Configured tracer or None if not initialized
    """
    global _tracer
    
    if _tracer is None:
        setup_tracing()
    
    return _tracer


@contextmanager
def trace_agent_operation(
    operation_name: str,
    agent_type: Optional[str] = None,
    agent_version: Optional[str] = None,
    claim_id: Optional[str] = None,
    **attributes
):
    """Context manager for tracing agent operations.
    
    Args:
        operation_name: Name of the operation being traced
        agent_type: Type of agent performing operation
        agent_version: Version of the agent
        claim_id: Associated claim ID
        **attributes: Additional span attributes
        
    Yields:
        The active span for additional instrumentation
    """
    tracer = get_tracer()
    
    if tracer is None:
        # Tracing not available, yield None
        yield None
        return
    
    with tracer.start_as_current_span(operation_name) as span:
        try:
            # Set standard attributes following OpenTelemetry semantic conventions
            span.set_attribute("gen_ai.operation.name", operation_name)
            span.set_attribute("gen_ai.system", "azure_ai_agents")
            
            if agent_type:
                span.set_attribute("gen_ai.agent.type", agent_type)
                span.set_attribute("gen_ai.agent.name", agent_type)
            
            if agent_version:
                span.set_attribute("gen_ai.agent.version", agent_version)
            
            if claim_id:
                span.set_attribute("insurance.claim_id", claim_id)
            
            # Add custom attributes
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, str(value))
            
            yield span
            
            # Mark as successful
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            # Record exception in span
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_llm_call(
    model_name: str,
    operation: str = "chat.completion",
    **attributes
):
    """Context manager for tracing LLM API calls.
    
    Args:
        model_name: Name of the model being called
        operation: Type of operation (chat.completion, embedding, etc.)
        **attributes: Additional span attributes
        
    Yields:
        The active span for recording token usage
    """
    tracer = get_tracer()
    
    if tracer is None:
        yield None
        return
    
    with tracer.start_as_current_span(f"gen_ai.{operation}") as span:
        try:
            span.set_attribute("gen_ai.system", "azure_openai")
            span.set_attribute("gen_ai.request.model", model_name)
            span.set_attribute("gen_ai.operation.name", operation)
            
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, str(value))
            
            yield span
            
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def record_token_usage(
    span,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int
):
    """Record token usage in a span.
    
    Args:
        span: Active OpenTelemetry span
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        total_tokens: Total tokens used
    """
    if span is None:
        return
    
    try:
        span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
        span.set_attribute("gen_ai.usage.total_tokens", total_tokens)
    except Exception as e:
        logger.error(f"Failed to record token usage in span: {e}")


@contextmanager
def trace_tool_call(
    tool_name: str,
    **attributes
):
    """Context manager for tracing agent tool invocations.
    
    Args:
        tool_name: Name of the tool being invoked
        **attributes: Additional span attributes
        
    Yields:
        The active span
    """
    tracer = get_tracer()
    
    if tracer is None:
        yield None
        return
    
    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        try:
            span.set_attribute("gen_ai.operation.name", "execute_tool")
            span.set_attribute("gen_ai.tool.name", tool_name)
            
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, str(value))
            
            yield span
            
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
