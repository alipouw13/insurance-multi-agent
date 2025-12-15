"""Token estimation utilities for when exact token tracking isn't available.

This module provides rough token estimates based on message content,
which is useful for LangGraph workflows that don't have direct token tracking.
"""
import re
from typing import Dict, Any


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.
    
    Uses a simple heuristic: ~4 characters per token for English text.
    This is a rough approximation used by OpenAI's tokenizer.
    
    Args:
        text: Input text string
        
    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Rough estimate: 4 characters per token
    # This matches OpenAI's rough guidance for English text
    char_count = len(text)
    estimated_tokens = char_count // 4
    
    # Add some buffer for special tokens and formatting
    return max(1, int(estimated_tokens * 1.1))


def estimate_message_tokens(messages: list) -> Dict[str, int]:
    """Estimate tokens for a list of messages.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens estimates
    """
    prompt_tokens = 0
    completion_tokens = 0
    
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get('content', '')
            role = msg.get('role', '')
            
            if isinstance(content, str):
                tokens = estimate_tokens(content)
                
                if role == 'assistant':
                    completion_tokens += tokens
                else:
                    prompt_tokens += tokens
    
    return {
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': prompt_tokens + completion_tokens
    }


def estimate_agent_step_tokens(input_data: Dict[str, Any], output_data: Dict[str, Any]) -> Dict[str, int]:
    """Estimate tokens for an agent step based on input/output data.
    
    Args:
        input_data: Agent input data
        output_data: Agent output data
        
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens estimates
    """
    # Estimate prompt tokens from input
    input_text = str(input_data) if input_data else ""
    prompt_tokens = estimate_tokens(input_text)
    
    # Estimate completion tokens from output
    output_text = ""
    if isinstance(output_data, dict):
        if 'content' in output_data:
            output_text = output_data['content']
        elif 'messages' in output_data:
            messages = output_data['messages']
            if isinstance(messages, list):
                output_text = " ".join(str(m.get('content', '')) for m in messages if isinstance(m, dict))
            else:
                output_text = str(messages)
        else:
            output_text = str(output_data)
    else:
        output_text = str(output_data)
    
    completion_tokens = estimate_tokens(output_text)
    
    return {
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': prompt_tokens + completion_tokens
    }
