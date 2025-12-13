"""Custom OpenTelemetry Span Processor for capturing token usage.

This processor intercepts OpenTelemetry spans from OpenAI instrumentation
and extracts token usage data to save to Cosmos DB.
"""
from __future__ import annotations

import logging
from typing import Optional

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanProcessor
from opentelemetry.trace import Status, StatusCode

from app.models.agent_models import TokenUsageRecord, ServiceType, OperationType
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)


class TokenUsageSpanProcessor(SpanProcessor):
    """Span processor that captures token usage from OpenAI calls."""
    
    def __init__(self, token_tracker=None):
        """Initialize the span processor.
        
        Args:
            token_tracker: TokenUsageTracker instance to record usage
        """
        self.token_tracker = token_tracker
        self._enabled = False
    
    def enable(self):
        """Enable token usage capture."""
        self._enabled = True
        logger.debug("Token usage capture enabled")
    
    def disable(self):
        """Disable token usage capture."""
        self._enabled = False
        logger.debug("Token usage capture disabled")
    
    def on_start(self, span: ReadableSpan, parent_context = None) -> None:
        """Called when a span starts (no-op for token capture)."""
        pass
    
    def on_end(self, span: ReadableSpan) -> None:
        """Called when a span ends - extract token usage here."""
        if not self._enabled:
            return
            
        if not self.token_tracker:
            logger.debug("Token tracker not available in span processor")
            return
        
        try:
            # Check if this is an OpenAI or Azure AI Agent span
            span_name = span.name
            attributes = span.attributes or {}
            
            # Check for gen_ai attributes
            has_gen_ai = any(key.startswith('gen_ai.') for key in attributes.keys())
            
            # Check for Azure AI Agent Service spans (from AIAgentsInstrumentor)
            is_azure_agent = (
                'gen_ai.system' in attributes and 
                attributes.get('gen_ai.system') == 'azure_ai_agents'
            ) or 'agent.' in span_name.lower() or has_gen_ai
            
            # Check for OpenAI spans (direct OpenAI calls)
            is_openai = any(indicator in span_name.lower() for indicator in ['openai', 'chat', 'completion', 'embedding'])
            
            if not (is_azure_agent or is_openai):
                return
            
            # Get token usage from span attributes
            # OpenTelemetry Gen AI Semantic Conventions (used by both instrumentors)
            prompt_tokens = attributes.get('gen_ai.usage.prompt_tokens', 0)
            completion_tokens = attributes.get('gen_ai.usage.completion_tokens', 0)
            
            # Alternative attribute names (for backward compatibility)
            if prompt_tokens == 0:
                prompt_tokens = attributes.get('llm.usage.prompt_tokens', 0)
            if completion_tokens == 0:
                completion_tokens = attributes.get('llm.usage.completion_tokens', 0)
            
            # Only record if we have actual token usage
            if prompt_tokens > 0 or completion_tokens > 0:
                model_name = attributes.get('gen_ai.request.model', 
                                          attributes.get('llm.request.model', 'unknown'))
                deployment = attributes.get('server.address', model_name)
                
                # Determine operation type from span name
                operation_type = "embedding" if "embedding" in span_name.lower() else "chat_completion"
                
                # Record the usage asynchronously
                import asyncio
                try:
                    # Try to get the running event loop (Python 3.10+)
                    try:
                        loop = asyncio.get_running_loop()
                        # If loop is running, create a task
                        task = loop.create_task(self.token_tracker.record_token_usage(
                            model_name=model_name,
                            deployment_name=deployment,
                            prompt_tokens=int(prompt_tokens),
                            completion_tokens=int(completion_tokens),
                            operation_type=operation_type
                        ))
                    except RuntimeError:
                        # No running loop - this shouldn't happen in FastAPI context
                        logger.warning(f"⚠️ No running event loop - cannot record token usage asynchronously")
                        logger.warning(f"⚠️ Token usage: {prompt_tokens}+{completion_tokens} tokens for {model_name} NOT saved")
                except Exception as e:
                    logger.error(f"❌ Error recording token usage: {e}", exc_info=True)
            else:
                logger.debug(f"No token usage in span {span_name}")
        
        except Exception as e:
            logger.error(f"Error capturing token usage from span: {e}")
    
    def shutdown(self) -> None:
        """Called on shutdown."""
        pass
    
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any buffered spans."""
        return True


# Global instance
_token_span_processor: Optional[TokenUsageSpanProcessor] = None


def get_token_span_processor() -> Optional[TokenUsageSpanProcessor]:
    """Get the global token span processor instance."""
    return _token_span_processor


def setup_token_span_processor(token_tracker) -> TokenUsageSpanProcessor:
    """Set up the token usage span processor.
    
    Args:
        token_tracker: TokenUsageTracker instance
        
    Returns:
        Configured span processor
    """
    global _token_span_processor
    
    if _token_span_processor is not None:
        logger.debug("Token span processor already configured")
        return _token_span_processor
    
    try:
        from opentelemetry import trace
        
        _token_span_processor = TokenUsageSpanProcessor(token_tracker)
        
        # Add the processor to the tracer provider
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, 'add_span_processor'):
            tracer_provider.add_span_processor(_token_span_processor)
            logger.info("✅ Token usage span processor configured")
        else:
            logger.warning("⚠️ Tracer provider does not support span processors")
        
        return _token_span_processor
        
    except Exception as e:
        logger.error(f"❌ Failed to setup token span processor: {e}")
        return None
