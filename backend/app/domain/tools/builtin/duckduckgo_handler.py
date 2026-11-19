"""
DuckDuckGo Web Search Tool Handler.

Provides real-time web search capabilities using DuckDuckGo.
No API key required - uses the ddgs library.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class DuckDuckGoTool:
    """
    DuckDuckGo web search tool for AI agents.

    Tags:
        - op:read
        - op:search
        - purpose:research
        - source:web
        - safe
        - text

    Operations:
        - search: Search the web using DuckDuckGo

    Features:
        - No API key required
        - AI-optimized concise results
        - Configurable result count
        - Region and time filtering
        - Graceful error handling
    """

    name = "DuckDuckGo"
    slug = "duckduckgo"
    capability = "web-search"
    description = "Search the web for real-time information using DuckDuckGo (no API key needed)"
    tags = [
        "op:read",
        "op:search",
        "purpose:research",
        "source:web",
        "safe",
        "text",
    ]
    icon = "search"
    color = "#DE5833"  # DuckDuckGo orange

    # Conservative defaults to avoid rate limiting
    MAX_RESULTS_DEFAULT = 5
    MAX_RESULTS_MAX = 15

    config_schema = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 15,
                "description": "Maximum number of search results to return",
            },
            "region": {
                "type": "string",
                "default": "wt-wt",
                "description": "Search region: 'wt-wt' (all), 'us-en', 'uk-en', 'de-de', 'fr-fr', etc.",
            },
            "time": {
                "type": "string",
                "enum": ["d", "w", "m", "y", ""],
                "default": "",
                "description": "Time filter: 'd' (day), 'w' (week), 'm' (month), 'y' (year), '' (any)",
            },
            "safe_search": {
                "type": "string",
                "enum": ["on", "moderate", "off"],
                "default": "moderate",
                "description": "Safe search level",
            },
        },
        "required": [],
    }

    arguments_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of search results to return",
            },
            "region": {
                "type": "string",
                "default": "wt-wt",
                "description": "Search region (e.g., 'wt-wt', 'us-en', 'uk-en')",
            },
            "time": {
                "type": "string",
                "enum": ["d", "w", "m", "y", ""],
                "default": "",
                "description": "Time filter: 'd' (day), 'w' (week), 'm' (month), 'y' (year), '' (any)",
            },
            "safe_search": {
                "type": "boolean",
                "default": True,
                "description": "Enable safe search filtering",
            },
        },
        "required": ["query"],
    }

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute DuckDuckGo web search.

        Args:
            config: Tool configuration (max_results, region, time, safe_search)
            **kwargs: Search parameters (query, max_results, region, time)

        Returns:
            Dictionary with success status and search results
        """
        # Validate query
        query = kwargs.get("query", "").strip()
        if not query:
            logger.warning("DuckDuckGo tool called with empty query")
            return {
                "success": False,
                "error": "No query provided. Please specify what you want to search for.",
                "error_type": "ValidationError",
                "user_message": "Please provide a search query.",
            }

        # Get parameters (kwargs override config)
        max_results = kwargs.get("max_results", config.get("max_results", self.MAX_RESULTS_DEFAULT))
        region = kwargs.get("region", config.get("region", "wt-wt"))
        time_filter = kwargs.get("time", config.get("time", ""))
        safe_search = kwargs.get("safe_search", config.get("safe_search", "moderate"))

        # Validate max_results — THE STRING GUARD (2026-08-24, Bob's
        # first search): the LLM passed max_results="10" (a string —
        # the schema says integer but tool-calling models are sloppy);
        # min("10", 20) crashed with the '<' TypeError and the search
        # failed. Coerce + clamp, never compare raw.
        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = self.MAX_RESULTS_DEFAULT
        max_results = max(1, min(max_results, self.MAX_RESULTS_MAX))

        logger.info(
            f"DuckDuckGo search: '{query}' (max_results={max_results}, region={region}, time={time_filter})"
        )

        try:
            # Run sync duckduckgo-search in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._search_sync,
                query,
                max_results,
                region,
                time_filter,
                safe_search,
            )

            if not results:
                return {
                    "success": True,
                    "query": query,
                    "results_count": 0,
                    "results": [],
                    "message": "No results found for this query.",
                }

            # Format results for LLM consumption
            formatted_results = []
            for i, r in enumerate(results, 1):
                formatted_results.append({
                    "rank": i,
                    "title": r.get("title", "Untitled"),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })

            response = {
                "success": True,
                "query": query,
                "results_count": len(formatted_results),
                "results": formatted_results,
            }

            logger.info(f"DuckDuckGo search complete: {len(formatted_results)} results")
            return response

        except ImportError:
            logger.error("ddgs library not installed")
            return {
                "success": False,
                "error": "DuckDuckGo search library is not installed. Please contact the administrator.",
                "error_type": "ConfigurationError",
                "user_message": "The DuckDuckGo search tool is not properly configured.",
            }
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Search failed: {str(e)}",
                "error_type": "UnknownError",
                "user_message": "An unexpected error occurred during the search. Please try again.",
            }

    def _search_sync(
        self,
        query: str,
        max_results: int,
        region: str,
        time_filter: str,
        safe_search: str,
    ) -> List[Dict[str, str]]:
        """
        Synchronous DuckDuckGo search (runs in thread pool).

        Args:
            query: Search query
            max_results: Maximum number of results
            region: Search region
            time_filter: Time filter (d/w/m/y/empty)
            safe_search: Safe search level

        Returns:
            List of result dicts with title, href, body
        """
        from ddgs import DDGS

        # Map safe_search string to boolean
        safe = safe_search != "off"

        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                region=region,
                safesearch="moderate" if safe else "off",
                timelimit=time_filter if time_filter else None,
                max_results=max_results,
            ))

        return results
