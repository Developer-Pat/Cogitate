"""
Provider Completion Service.

Unified interface for LLM completions with fallback support.
"""

import logging
from app.domain.providers.litellm_route import api_base_for, litellm_model_string
import time
from typing import Optional, List, Dict, Any, AsyncGenerator


logger = logging.getLogger(__name__)


class CompletionRequest:
    """
    Completion request model.

    Encapsulates all parameters needed for a completion request.
    """

    def __init__(
        self,
        messages: List[Dict[str, str]],
        model: str,
        provider: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize completion request.

        Args:
            messages: List of message dictionaries
            model: Model name
            provider: Provider name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            stream: Whether to stream response
            **kwargs: Additional provider-specific parameters
        """
        self.messages = messages
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.stream = stream
        # THE ADDRESS this request dials (2026-10-12, stage 2) — handed in by the caller that
        # resolved the chain, because a value object cannot look a row up and must not carry a copy.
        self.endpoint = endpoint
        self.extra_params = kwargs

    def to_litellm_kwargs(self) -> Dict[str, Any]:
        """
        Convert to LiteLLM kwargs format.

        Returns:
            Dictionary of LiteLLM parameters
        """
        # The model string comes from the ONE mapping (`litellm_route`): the litellm handler this
        # provider speaks. The address is the CALLER's (2026-10-12, stage 2) — it resolved the chain
        # and handed each request its own; this value object invents nothing.
        model_name = litellm_model_string(self.provider, self.model)
        api_base = self.endpoint
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": self.messages,
        }

        # ollama_cloud needs the custom api_base + its Bearer key
        if api_base:
            # THE ROOT THE HANDLER NEEDS, not the table's value verbatim: `ollama_cloud` rides the
            # tool-capable `ollama_chat` handler, which composes `{api_base}/api/chat` itself.
            kwargs["api_base"] = api_base_for(model_name, api_base)
            from app.core.config import get_settings
            cloud_key = get_settings().ollama_cloud_api_key or None
            if cloud_key:
                kwargs["api_key"] = cloud_key

        # Add optional parameters
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p

        # Add extra parameters
        kwargs.update(self.extra_params)

        return kwargs


class CompletionResponse:
    """
    Completion response model.

    Encapsulates response data including usage statistics.
    """

    def __init__(
        self,
        content: str,
        model: str,
        provider: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        response_time_ms: int = 0,
        success: bool = True,
        error_message: Optional[str] = None,
        raw_response: Optional[Any] = None,
    ):
        """
        Initialize completion response.

        Args:
            content: Response content
            model: Model used
            provider: Provider used
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total tokens used
            response_time_ms: Response time in milliseconds
            success: Whether request was successful
            error_message: Error message if failed
            raw_response: Raw provider response
        """
        self.content = content
        self.model = model
        self.provider = provider
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.response_time_ms = response_time_ms
        self.success = success
        self.error_message = error_message
        self.raw_response = raw_response

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "error_message": self.error_message,
        }


class ProviderCompletionService:
    """
    Unified completion service with provider abstraction.

    Features:
    - Unified interface for all providers via LiteLLM
    - Automatic fallback chain
    - Rate limiting
    - Usage tracking
    - Error handling and retry logic
    """

    def __init__(self):
        """Initialize completion service."""
        self._litellm_acompletion = None
        self._initialize_litellm()

    def _initialize_litellm(self):
        """Initialize LiteLLM."""
        try:
            from litellm import acompletion
            self._litellm_acompletion = acompletion
            logger.info("✅ LiteLLM initialized for completions")
        except ImportError:
            logger.error("❌ LiteLLM not installed - completions will fail")
            self._litellm_acompletion = None

    async def complete(
        self,
        request: CompletionRequest,
        fallback_chain: Optional[List[str]] = None,
        max_retries: int = 1,
        endpoints: Optional[Dict[str, Optional[str]]] = None,
    ) -> CompletionResponse:
        """
        Send completion request with optional fallback.

        Args:
            request: Completion request
            fallback_chain: List of fallback providers in order
            max_retries: Maximum retry attempts per provider

        Returns:
            Completion response
        """
        start_time = time.time()

        # Build provider list (primary + fallbacks)
        providers_to_try = [request.provider]
        if fallback_chain:
            providers_to_try.extend(fallback_chain)

        last_error = None

        # THE FALLBACK WARNING (2026-09-01, the user's 'silent
        # fallbacks are bad'): the user SEES the failover when the
        # primary isn't the first in line.
        if fallback_chain:
            from app.domain.messaging.services import publish_warning

            publish_warning(
                "The provider fell back",
                f"The primary ({request.provider}) failed or is unavailable — "
                f"trying {' → '.join(fallback_chain)}.",
                kind="provider-fallback",
            )

        # Try each provider in order
        for provider in providers_to_try:
            try:
                logger.info(f"🔄 Attempting completion with {provider}/{request.model}")

                # Create request for this provider
                provider_request = CompletionRequest(
                    messages=request.messages,
                    model=request.model,
                    provider=provider,
                    endpoint=(endpoints or {}).get(provider),
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                    stream=request.stream,
                    **request.extra_params
                )

                # Make the request
                response = await self._complete_with_provider(
                    provider_request,
                    max_retries=max_retries
                )

                if response.success:
                    # Calculate response time
                    response.response_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"✅ Completion successful with {provider}")
                    return response
                else:
                    logger.warning(f"⚠️ {provider} completion failed: {response.error_message}")
                    last_error = response.error_message

            except Exception as e:
                logger.error(f"❌ {provider} completion error: {e}")
                last_error = str(e)
                continue

        # All providers failed
        response_time_ms = int((time.time() - start_time) * 1000)
        return CompletionResponse(
            content="",
            model=request.model,
            provider=request.provider,
            response_time_ms=response_time_ms,
            success=False,
            error_message=f"All providers failed. Last error: {last_error}",
        )

    async def _complete_with_provider(
        self,
        request: CompletionRequest,
        max_retries: int = 1,
    ) -> CompletionResponse:
        """
        Complete request with specific provider.

        Args:
            request: Completion request
            max_retries: Maximum retry attempts

        Returns:
            Completion response
        """
        if not self._litellm_acompletion:
            return CompletionResponse(
                content="",
                model=request.model,
                provider=request.provider,
                success=False,
                error_message="LiteLLM not initialized",
            )

        last_error = None

        for attempt in range(max_retries):
            try:
                # Build LiteLLM kwargs
                litellm_kwargs = request.to_litellm_kwargs()

                # Call LiteLLM
                response = await self._litellm_acompletion(**litellm_kwargs)

                # Extract response content
                message = response.choices[0].message if response.choices else None
                content = getattr(message, 'content', None) if message else None
                
                # Handle reasoning models (like Nemotron) that use reasoning_content
                if not content and message:
                    content = getattr(message, 'reasoning_content', None)
                
                content = content or ""

                # Extract usage statistics
                usage = getattr(response, 'usage', None)
                prompt_tokens = getattr(usage, 'prompt_tokens', 0) if usage else 0
                completion_tokens = getattr(usage, 'completion_tokens', 0) if usage else 0
                total_tokens = getattr(usage, 'total_tokens', 0) if usage else 0

                return CompletionResponse(
                    content=content,
                    model=request.model,
                    provider=request.provider,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    success=True,
                    raw_response=response,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ Attempt {attempt + 1}/{max_retries} failed for {request.provider}: {e}")

                if attempt < max_retries - 1:
                    # Wait before retry (exponential backoff)
                    import asyncio
                    await asyncio.sleep(2 ** attempt)

        # All retries failed
        return CompletionResponse(
            content="",
            model=request.model,
            provider=request.provider,
            success=False,
            error_message=last_error,
        )

    async def complete_stream(
        self,
        request: CompletionRequest,
        fallback_chain: Optional[List[str]] = None,
        endpoints: Optional[Dict[str, Optional[str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream completion response using LiteLLM native streaming.

        Args:
            request: Completion request
            fallback_chain: List of fallback providers

        Yields:
            Response content chunks
        """
        # Build provider list (primary + fallbacks)
        providers_to_try = [request.provider]
        if fallback_chain:
            providers_to_try.extend(fallback_chain)

        last_error = None

        # Try each provider in order
        for provider in providers_to_try:
            try:
                logger.info(f"🔄 Streaming completion with {provider}/{request.model}")

                # Create request for this provider
                provider_request = CompletionRequest(
                    messages=request.messages,
                    model=request.model,
                    provider=provider,
                    endpoint=(endpoints or {}).get(provider),
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                    stream=True,  # Enable streaming
                    **request.extra_params
                )

                # Stream with this provider
                async for chunk in self._stream_with_provider(provider_request):
                    yield chunk

                # Success - return after streaming completes
                return

            except Exception as e:
                logger.error(f"❌ {provider} streaming error: {e}")
                last_error = str(e)
                continue

        # All providers failed
        yield f"Error: All providers failed. Last error: {last_error}"

    async def _stream_with_provider(
        self,
        request: CompletionRequest,
    ) -> AsyncGenerator[str, None]:
        """
        Stream with specific provider using LiteLLM.

        Args:
            request: Completion request

        Yields:
            Response content chunks
        """
        if not self._litellm_acompletion:
            yield "Error: LiteLLM not initialized"
            return

        try:
            # Build LiteLLM kwargs with streaming enabled
            litellm_kwargs = request.to_litellm_kwargs()
            litellm_kwargs["stream"] = True

            # Call LiteLLM streaming API
            stream_response = await self._litellm_acompletion(**litellm_kwargs)

            # Iterate over streaming chunks
            async for chunk in stream_response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"❌ Streaming error with {request.provider}: {e}")
            raise


# Singleton instance
provider_completion_service = ProviderCompletionService()
