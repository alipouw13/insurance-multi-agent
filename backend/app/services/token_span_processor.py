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
            
            # Check for Azure AI Agent Service spans (from AIAgentsInstrumentor)
            is_azure_agent = (
                'gen_ai.system' in attributes and 
                attributes.get('gen_ai.system') == 'azure_ai_agents'
            ) or 'agent.' in span_name.lower()
            
            # Check for OpenAI spans (direct OpenAI calls)
            is_openai = any(indicator in span_name.lower() for indicator in ['openai', 'chat', 'completion', 'embedding'])
            
            if not (is_azure_agent or is_openai):
                return
            
            logger.info(f"🔍 Span processor examining span: {span_name} (azure_agent={is_azure_agent}, openai={is_openai})")
            
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
                
                logger.info(f"💾 Capturing token usage: {prompt_tokens} prompt + {completion_tokens} completion tokens (model={model_name})")
                
                # Record the usage asynchronously
                import asyncio
                try:
                    # Try to get the current event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, create a task
                        task = loop.create_task(self.token_tracker.record_token_usage(
                            model_name=model_name,
                            deployment_name=deployment,
                            prompt_tokens=int(prompt_tokens),
                            completion_tokens=int(completion_tokens),
                            operation_type=operation_type
                        ))
                        logger.info(f"✅ Created task to save token usage to Cosmos DB")
                    else:
                        # If no loop is running, use asyncio.run
                        asyncio.run(self.token_tracker.record_token_usage(
                            model_name=model_name,
                            deployment_name=deployment,
                            prompt_tokens=int(prompt_tokens),
                            completion_tokens=int(completion_tokens),
                            operation_type=operation_type
                        ))
                        logger.info(f"✅ Saved token usage to Cosmos DB")
                except RuntimeError as e:
                    # No event loop available
                    logger.error(f"❌ Could not record token usage - no event loop available: {e}")
                except Exception as e:
                    logger.error(f"❌ Error recording token usage: {e}")
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
