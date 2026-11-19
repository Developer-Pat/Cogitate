"""
Wikipedia Research Tool Handler.

Provides Wikipedia search and article retrieval.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from time import time
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class RateLimiter:
    """Client-side rate limiter for Wikipedia API calls."""

    def __init__(self, calls_per_second: int = 50):
        """
        Initialize rate limiter.

        Args:
            calls_per_second: Maximum API calls per second
        """
        self.calls_per_second = calls_per_second
        self.calls: deque = deque(maxlen=calls_per_second)

    async def acquire(self):
        """Wait if rate limit would be exceeded."""
        now = time()

        # Remove old calls (older than 1 second)
        while self.calls and self.calls[0] < now - 1:
            self.calls.popleft()

        # Wait if at limit
        if len(self.calls) >= self.calls_per_second:
            wait_time = 1 - (now - self.calls[0])
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        self.calls.append(time())


class WikipediaTool:
    """
    Wikipedia research tool.

    Tags:
        - op:read
        - op:search
        - purpose:research
        - source:wikipedia
        - safe
        - text

    Operations:
        - search: Search Wikipedia articles
        - summary: Get article summary
        - full: Get full article content
        - random: Get random article
    """

    name = "Wikipedia"
    slug = "wikipedia"
    capability = "wiki-lookup"
    description = "Search and retrieve Wikipedia articles"
    tags = [
        "op:read",
        "op:search",
        "purpose:research",
        "source:wikipedia",
        "safe",
        "text",
    ]
    icon = "book-open"
    color = "#000000"  # Wikipedia black

    # Rate limiter instance (shared across tool instances)
    _rate_limiter: RateLimiter | None = None

    config_schema = {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "default": "en",
                "description": "Wikipedia language code (e.g., 'en', 'es', 'fr')",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "Maximum search results to return",
            },
            "include_images": {
                "type": "boolean",
                "default": True,
                "description": "Include article thumbnails in results",
            },
        },
    }

    arguments_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string or article title to look up on Wikipedia",
            },
            "operation": {
                "type": "string",
                "enum": ["search", "summary", "full", "random"],
                "description": "Wikipedia operation to perform",
            },
            "title": {
                "type": "string",
                "description": "Exact article title (alternative to query for summary/full operations)",
            },
            "lang": {
                "type": "string",
                "description": "Wikipedia language code override for this request (e.g., 'en', 'es', 'fr')",
            },
            "max_results": {
                "type": "integer",
                "description": "Override max search results for this request",
            },
        },
        "required": ["query"],
    }

    @classmethod
    def get_rate_limiter(cls) -> RateLimiter:
        """Get or create shared rate limiter instance."""
        if cls._rate_limiter is None:
            cls._rate_limiter = RateLimiter(calls_per_second=50)
        return cls._rate_limiter

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute Wikipedia operation.

        Args:
            config: Tool configuration
            **kwargs: Operation parameters (query, operation, title, etc.)

        Returns:
            Dictionary with success status and result

        Note:
            - Handles empty/missing arguments gracefully
            - Provides capability error messages for unsupported features
        """
        # Handle empty/missing arguments - provide helpful error
        if not kwargs or len(kwargs) == 0:
            logger.warning("⚠️ Wikipedia tool called with no arguments - query is required")
            return {
                "success": False,
                "error": "No query provided. Please specify what you want to search for or which article to retrieve.",
                "error_type": "ValidationError",
                "user_message": "Please tell me what topic you'd like to research on Wikipedia.",
            }

        operation = kwargs.get("operation", "search")
        query = kwargs.get("query", "")
        title = kwargs.get("title", "")

        # Validate input based on operation
        if operation in ["search", "summary"] and not query and not title:
            logger.warning("⚠️ Wikipedia tool: empty query provided")
            return {
                "success": False,
                "error": "Query or title is required",
                "error_type": "ValidationError",
                "user_message": "Please provide a search query or article title.",
            }

        # Check for capability errors - things we explicitly don't support
        # This helps developers identify feature gaps
        video_request = kwargs.get("video", False) or kwargs.get("watch", False)
        if video_request:
            logger.warning(
                "🚫 CAPABILITY_ERROR: Wikipedia tool doesn't support video playback. "
                "Tool only provides text content from Wikipedia articles."
            )
            return {
                "success": False,
                "error": "capability_not_supported",
                "error_type": "CapabilityError",
                "error_details": {
                    "requested_feature": "video playback",
                    "supported_features": ["text search", "article summary", "full article text"],
                    "developer_note": "Video playback not implemented",
                },
                "user_message": "I can only retrieve text content from Wikipedia articles. I cannot play videos.",
            }

        # Dispatch to appropriate operation
        if operation == "search":
            return await self._search(config, query or title)
        elif operation == "summary":
            return await self._summary(config, title or query)
        elif operation == "full":
            return await self._full_article(config, title or query)
        elif operation == "random":
            return await self._random(config)
        else:
            # Unknown operation - provide helpful error with available operations
            available_ops = ["search", "summary", "full", "random"]
            error_msg = (
                f"Unknown operation: '{operation}'. "
                f"Available operations: {', '.join(available_ops)}. "
                f"For searching, use operation='search' with a query."
            )
            logger.warning(f"⚠️ Wikipedia tool: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "error_type": "ValidationError",
            }

    async def _search(self, config: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Search Wikipedia articles.

        Args:
            config: Tool configuration
            query: Search query string

        Returns:
            Dictionary with search results
        """
        lang = config.get("language", "en")
        max_results = config.get("max_results", 5)
        include_images = config.get("include_images", True)

        # Validate language code
        if not self._is_valid_language_code(lang):
            logger.warning(f"⚠️ Invalid language code: {lang}. Using 'en' as fallback.")
            lang = "en"

        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json",
        }

        try:
            # Apply rate limiting
            await self.get_rate_limiter().acquire()

            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "ART (Advanced Research Technologies)"
                }
            ) as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            # Process results
            search_results = []
            for item in data.get("query", {}).get("search", []):
                result = {
                    "title": item["title"],
                    "snippet": item["snippet"],
                    "wordcount": item.get("wordcount", 0),
                }
                if include_images and item.get("thumbnail"):
                    result["thumbnail"] = item["thumbnail"]

                search_results.append(result)

            logger.info(f"✅ Wikipedia search for '{query}' returned {len(search_results)} results")

            return {
                "success": True,
                "operation": "search",
                "query": query,
                "results": search_results,
                "count": len(search_results),
                "attribution": self._get_attribution(),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Wikipedia search HTTP error: {e.response.status_code}")
            if e.response.status_code == 429:
                return {
                    "success": False,
                    "error": "Rate limit exceeded. Please try again in a moment.",
                    "error_type": "RateLimitError",
                }
            return {
                "success": False,
                "error": f"Search failed: {e.response.status_code}",
                "error_type": "HTTPError",
            }
        except httpx.RequestError as e:
            logger.error(f"❌ Wikipedia search request error: {str(e)}")
            return {
                "success": False,
                "error": "Cannot connect to Wikipedia. Please check your internet connection.",
                "error_type": "NetworkError",
            }
        except Exception as e:
            logger.error(f"❌ Wikipedia search unexpected error: {str(e)}")
            return {
                "success": False,
                "error": f"Search failed: {str(e)}",
                "error_type": "UnexpectedError",
            }

    async def _summary(self, config: Dict[str, Any], title: str) -> Dict[str, Any]:
        """
        Get article summary from Wikipedia REST API.

        Args:
            config: Tool configuration
            title: Article title

        Returns:
            Dictionary with article summary
        """
        lang = config.get("language", "en")
        include_images = config.get("include_images", True)

        # Validate language code
        if not self._is_valid_language_code(lang):
            logger.warning(f"⚠️ Invalid language code: {lang}. Using 'en' as fallback.")
            lang = "en"

        # Use Wikipedia REST API summary endpoint
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{self._url_encode(title)}"
        params = {"redirect": "1"}

        try:
            # Apply rate limiting
            await self.get_rate_limiter().acquire()

            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "ART (Advanced Research Technologies)"
                }
            ) as client:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 404:
                    logger.warning(f"⚠️ Wikipedia article not found: {title}")
                    return {
                        "success": False,
                        "error": "Article not found",
                        "error_type": "NotFound",
                        "user_message": f"I couldn't find an article titled '{title}' on Wikipedia.",
                    }

                if response.status_code == 429:
                    return {
                        "success": False,
                        "error": "Rate limit exceeded. Please try again in a moment.",
                        "error_type": "RateLimitError",
                    }

                response.raise_for_status()
                data = response.json()

            # Check if this is a disambiguation page
            if data.get("type") == "disambiguation":
                logger.info(f"ℹ️ Wikipedia page is disambiguation: {title}")
                return {
                    "success": False,
                    "error": "Disambiguation page",
                    "error_type": "Disambiguation",
                    "user_message": f"'{title}' has multiple meanings. Please be more specific.",
                    "is_disambiguation": True,
                }

            result = {
                "success": True,
                "operation": "summary",
                "title": data["title"],
                "extract": data.get("extract", ""),
                "description": data.get("description", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "attribution": self._get_attribution(),
            }

            if include_images and data.get("thumbnail"):
                result["thumbnail"] = data["thumbnail"]

            if data.get("timestamp"):
                result["last_edited"] = data["timestamp"]

            logger.info(f"✅ Retrieved Wikipedia summary: {data['title']}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Wikipedia summary HTTP error: {e.response.status_code}")
            return {
                "success": False,
                "error": f"Failed to retrieve article: {e.response.status_code}",
                "error_type": "HTTPError",
            }
        except httpx.RequestError as e:
            logger.error(f"❌ Wikipedia summary request error: {str(e)}")
            return {
                "success": False,
                "error": "Cannot connect to Wikipedia. Please check your internet connection.",
                "error_type": "NetworkError",
            }
        except Exception as e:
            logger.error(f"❌ Wikipedia summary unexpected error: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to retrieve article: {str(e)}",
                "error_type": "UnexpectedError",
            }

    async def _full_article(self, config: Dict[str, Any], title: str) -> Dict[str, Any]:
        """
        Get full article content from Wikipedia.

        Args:
            config: Tool configuration
            title: Article title

        Returns:
            Dictionary with full article content
        """
        lang = config.get("language", "en")

        # Validate language code
        if not self._is_valid_language_code(lang):
            logger.warning(f"⚠️ Invalid language code: {lang}. Using 'en' as fallback.")
            lang = "en"

        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "explaintext": "1",  # Return plain text instead of HTML
            "format": "json",
            "redirects": "1",  # Follow redirects
        }

        try:
            # Apply rate limiting
            await self.get_rate_limiter().acquire()

            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "ART (Advanced Research Technologies)"
                }
            ) as client:
                response = await client.get(url, params=params, timeout=15.0)
                response.raise_for_status()
                data = response.json()

            # Extract article content
            pages = data.get("query", {}).get("pages", {})
            page_id = next(iter(pages.keys()), None)

            if not page_id or page_id == "-1":
                logger.warning(f"⚠️ Wikipedia article not found: {title}")
                return {
                    "success": False,
                    "error": "Article not found",
                    "error_type": "NotFound",
                    "user_message": f"I couldn't find an article titled '{title}' on Wikipedia.",
                }

            page_data = pages[page_id]
            extract = page_data.get("extract", "")

            if not extract:
                logger.warning(f"⚠️ Wikipedia article has no content: {title}")
                return {
                    "success": False,
                    "error": "Article has no content",
                    "error_type": "EmptyContent",
                }

            logger.info(f"✅ Retrieved full Wikipedia article: {page_data['title']}")

            return {
                "success": True,
                "operation": "full",
                "title": page_data["title"],
                "content": extract,
                "url": f"https://{lang}.wikipedia.org/wiki/{self._url_encode(page_data['title'])}",
                "attribution": self._get_attribution(),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Wikipedia full article HTTP error: {e.response.status_code}")
            if e.response.status_code == 429:
                return {
                    "success": False,
                    "error": "Rate limit exceeded. Please try again in a moment.",
                    "error_type": "RateLimitError",
                }
            return {
                "success": False,
                "error": f"Failed to retrieve article: {e.response.status_code}",
                "error_type": "HTTPError",
            }
        except httpx.RequestError as e:
            logger.error(f"❌ Wikipedia full article request error: {str(e)}")
            return {
                "success": False,
                "error": "Cannot connect to Wikipedia. Please check your internet connection.",
                "error_type": "NetworkError",
            }
        except Exception as e:
            logger.error(f"❌ Wikipedia full article unexpected error: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to retrieve article: {str(e)}",
                "error_type": "UnexpectedError",
            }

    async def _random(self, config: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Get a random Wikipedia article.

        Args:
            config: Tool configuration
            max_retries: Maximum retries if disambiguation page is returned

        Returns:
            Dictionary with random article data
        """
        lang = config.get("language", "en")

        # Validate language code
        if not self._is_valid_language_code(lang):
            logger.warning(f"⚠️ Invalid language code: {lang}. Using 'en' as fallback.")
            lang = "en"

        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "random",
            "rnnamespace": "0",  # Only main articles (no talk pages, etc.)
            "rnlimit": "1",
            "format": "json",
        }

        try:
            # Apply rate limiting
            await self.get_rate_limiter().acquire()

            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "ART (Advanced Research Technologies)"
                }
            ) as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            random_items = data.get("query", {}).get("random", [])
            if not random_items:
                return {
                    "success": False,
                    "error": "No random article found",
                    "error_type": "NotFound",
                }

            random_item = random_items[0]
            title = random_item["title"]

            # Get summary for the random article
            result = await self._summary(config, title)

            # If we got a disambiguation page, retry with a different random article
            if result.get("success") is False and result.get("error_type") == "Disambiguation":
                logger.info(f"🔁 Random article '{title}' was disambiguation, retrying... ({max_retries} left)")
                if max_retries > 0:
                    return await self._random(config, max_retries - 1)
                else:
                    return {
                        "success": False,
                        "error": "Got disambiguation page after multiple retries",
                        "error_type": "Disambiguation",
                        "user_message": "Could not find a suitable random article. Please try again.",
                    }

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Wikipedia random article HTTP error: {e.response.status_code}")
            return {
                "success": False,
                "error": f"Failed to get random article: {e.response.status_code}",
                "error_type": "HTTPError",
            }
        except httpx.RequestError as e:
            logger.error(f"❌ Wikipedia random article request error: {str(e)}")
            return {
                "success": False,
                "error": "Cannot connect to Wikipedia. Please check your internet connection.",
                "error_type": "NetworkError",
            }
        except Exception as e:
            logger.error(f"❌ Wikipedia random article unexpected error: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get random article: {str(e)}",
                "error_type": "UnexpectedError",
            }

    def _is_valid_language_code(self, lang: str) -> bool:
        """
        Validate language code.

        Args:
            lang: Language code to validate

        Returns:
            True if valid, False otherwise
        """
        # Basic validation - 2 letter codes are most common
        if not lang or len(lang) < 2 or len(lang) > 3:
            return False
        return lang.isalpha()

    def _url_encode(self, text: str) -> str:
        """
        URL encode text for Wikipedia API.

        Args:
            text: Text to encode

        Returns:
            URL encoded text with spaces as underscores
        """
        # Wikipedia uses underscores for spaces in URLs
        return text.replace(" ", "_")

    def _get_attribution(self) -> str:
        """
        Get Wikipedia attribution string.

        Returns:
            Attribution text
        """
        return (
            "Content from Wikipedia is licensed under CC-BY-SA 4.0. "
            "Source: https://www.wikipedia.org/"
        )
