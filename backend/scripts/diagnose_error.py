"""
Error Diagnostic Utility.

Captures and displays detailed error information from LiteLLM errors.
Use this to understand exactly what went wrong with provider requests.
"""

import json
from typing import Any, Dict


def extract_error_details(error: Exception) -> Dict[str, Any]:
    """
    Extract detailed information from a LiteLLM error.
    
    Args:
        error: The exception to analyze
        
    Returns:
        Dictionary with all available error details
    """
    details = {
        "error_type": type(error).__name__,
        "error_module": type(error).__module__,
        "message": str(error),
    }
    
    # Extract LiteLLM-specific attributes
    litellm_attrs = [
        "llm_provider", "model", "status_code", "code", "type",
        "param", "request_id", "response", "body", "headers",
        "num_retries", "max_retries", "litellm_debug_info"
    ]
    
    for attr in litellm_attrs:
        if hasattr(error, attr):
            try:
                value = getattr(error, attr)
                if value is not None:
                    # Convert response objects to string
                    if hasattr(value, '__class__') and 'Response' in value.__class__.__name__:
                        details[attr] = str(value)
                    else:
                        details[attr] = value
            except Exception:
                details[attr] = "<error reading attribute>"
    
    # Check for response body details
    if hasattr(error, 'response') and error.response is not None:
        try:
            response = error.response
            details["response_status"] = response.status_code
            details["response_reason"] = response.reason_phrase if hasattr(response, 'reason_phrase') else None
            
            # Try to read response body
            if hasattr(response, 'text'):
                details["response_body"] = response.text[:500]  # Limit to 500 chars
            elif hasattr(response, 'content'):
                details["response_body"] = str(response.content)[:500]
        except Exception as e:
            details["response_error"] = f"Could not read response: {e}"
    
    # Check for request details
    if hasattr(error, 'request') and error.request is not None:
        try:
            request = error.request
            details["request_method"] = request.method if hasattr(request, 'method') else None
            details["request_url"] = str(request.url) if hasattr(request, 'url') else None
        except Exception as e:
            details["request_error"] = f"Could not read request: {e}"
    
    return details


def format_error_report(details: Dict[str, Any]) -> str:
    """
    Format error details into a human-readable report.
    
    Args:
        details: Error details dictionary
        
    Returns:
        Formatted report string
    """
    lines = [
        "=" * 70,
        "ERROR DIAGNOSTIC REPORT",
        "=" * 70,
        "",
        "ERROR TYPE",
        "-" * 70,
        f"  Type: {details.get('error_type', 'Unknown')}",
        f"  Module: {details.get('error_module', 'Unknown')}",
        f"  Code: {details.get('code', details.get('status_code', 'N/A'))}",
        "",
        "MESSAGE",
        "-" * 70,
        f"  {details.get('message', 'No message')}",
        "",
        "PROVIDER & MODEL",
        "-" * 70,
        f"  Provider: {details.get('llm_provider', 'Unknown')}",
        f"  Model: {details.get('model', 'Unknown')}",
        "",
        "HTTP DETAILS",
        "-" * 70,
        f"  Status Code: {details.get('status_code', 'N/A')}",
        f"  Error Type: {details.get('type', 'N/A')}",
        f"  Request ID: {details.get('request_id', 'N/A')}",
    ]
    
    if details.get('response_status'):
        lines.extend([
            "",
            "RESPONSE DETAILS",
            "-" * 70,
            f"  Status: {details['response_status']}",
            f"  Reason: {details.get('response_reason', 'N/A')}",
        ])
        
        if details.get('response_body'):
            lines.extend([
                "",
                "  Response Body:",
                f"  {details['response_body']}",
            ])
    
    if details.get('request_url'):
        lines.extend([
            "",
            "REQUEST DETAILS",
            "-" * 70,
            f"  Method: {details.get('request_method', 'N/A')}",
            f"  URL: {details['request_url']}",
        ])
    
    # Add retry information if available
    if details.get('num_retries') is not None:
        lines.extend([
            "",
            "RETRY INFORMATION",
            "-" * 70,
            f"  Attempts: {details['num_retries']}",
            f"  Max Retries: {details.get('max_retries', 'N/A')}",
        ])
    
    # Add debug info if available
    if details.get('litellm_debug_info'):
        lines.extend([
            "",
            "DEBUG INFORMATION",
            "-" * 70,
            f"  {details['litellm_debug_info']}",
        ])
    
    # Add interpretation
    lines.extend([
        "",
        "INTERPRETATION",
        "-" * 70,
    ])
    
    status_code = details.get('status_code', details.get('code'))
    error_type = details.get('type', '')
    
    if status_code == 429 or 'rate_limit' in error_type.lower() or 'throttling' in error_type.lower():
        lines.extend([
            "  ⚠️  RATE LIMIT EXCEEDED",
            "  ",
            "  What happened:",
            "  - The provider rejected your request due to rate limiting",
            "  - This is NOT a problem with your code",
            "  ",
            "  Possible causes:",
            "  1. Free tier limits: Many providers have strict limits on free tiers",
            "  2. Too many requests: You may have exceeded requests/minute or requests/day",
            "  3. Shared limits: If using a shared API key, others may have used the quota",
            "  4. Temporary spike: Provider may be experiencing high load",
            "  ",
            "  Solutions:",
            "  - Wait a few minutes and retry",
            "  - Add your own API key (see provider settings)",
            "  - Switch to a different model/provider",
            "  - Implement retry logic with exponential backoff",
        ])
    elif status_code == 401:
        lines.extend([
            "  ❌ AUTHENTICATION FAILED",
            "  ",
            "  What happened:",
            "  - Your API key is missing, invalid, or expired",
            "  ",
            "  Solutions:",
            "  - Check your API key configuration",
            "  - Verify the key hasn't expired",
            "  - Ensure the key has permissions for this model",
        ])
    elif status_code == 403:
        lines.extend([
            "  ❌ PERMISSION DENIED",
            "  ",
            "  What happened:",
            "  - Your API key doesn't have permission for this resource",
            "  ",
            "  Solutions:",
            "  - Check model access permissions",
            "  - Verify your subscription tier",
            "  - Contact provider support",
        ])
    elif status_code == 404:
        lines.extend([
            "  ❌ MODEL NOT FOUND",
            "  ",
            "  What happened:",
            "  - The requested model doesn't exist or isn't available",
            "  ",
            "  Solutions:",
            "  - Check the model name spelling",
            "  - Verify the model is available from this provider",
            "  - Try a different model",
        ])
    elif status_code == 500 or status_code == 502 or status_code == 503:
        lines.extend([
            "  ❌ PROVIDER SERVER ERROR",
            "  ",
            "  What happened:",
            "  - The provider's server encountered an error",
            "  - This is a temporary issue on their end",
            "  ",
            "  Solutions:",
            "  - Wait and retry",
            "  - Try a different provider",
            "  - Check provider status page",
        ])
    else:
        lines.extend([
            f"  ⚠️  UNKNOWN ERROR (Status: {status_code or 'N/A'})",
            "  ",
            "  What happened:",
            "  - An unexpected error occurred",
            "  ",
            "  Solutions:",
            "  - Check the error message above",
            "  - Review provider documentation",
            "  - Try a different model/provider",
        ])
    
    lines.extend([
        "",
        "=" * 70,
    ])
    
    return "\n".join(lines)


def diagnose_litellm_error(error: Exception) -> None:
    """
    Diagnose and print a detailed error report for a LiteLLM error.
    
    Args:
        error: The exception to diagnose
    """
    details = extract_error_details(error)
    report = format_error_report(details)
    print(report)
    
    # Also output JSON for programmatic use
    print("\n\nRAW JSON (for programmatic use):")
    print(json.dumps(details, indent=2, default=str))


if __name__ == "__main__":
    # Demo with sample error
    from litellm import RateLimitError
    
    print("DEMO: Diagnosing a RateLimitError\n")
    
    error = RateLimitError(
        message="z-ai/glm-4.5-air:free is temporarily rate-limited upstream. Please retry shortly.",
        llm_provider="openrouter",
        model="z-ai/glm-4.5-air:free"
    )
    
    diagnose_litellm_error(error)
