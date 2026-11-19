"""
Provider domain service.

Business logic for provider operations with LiteLLM integration.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken as FernetInvalidToken

logger = logging.getLogger(__name__)

#: The key file, relative to the installation's data dir. ONE key per install,
#: generated on first use — see `EncryptionService._load_or_create_key`.
KEY_FILE_NAME = ".encryption_key"


class EncryptionService:
    """Service for encrypting and decrypting API keys."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service.

        Args:
            encryption_key: Fernet encryption key. If None, falls back to
                           settings.cogitate_encryption_key (from .env
                           COGITATE_ENCRYPTION_KEY). Raises if no key is
                           available — a random per-instance key would
                           silently break cross-request decryption.
        """
        key = encryption_key
        if not key:
            try:
                from app.core.config import get_settings
                key = get_settings().cogitate_encryption_key
            except Exception as e:
                logger.error(f"Failed to load encryption key from settings: {e}")
                key = None
        if not key:
            key = self._load_or_create_key()
        self.key = key.encode()
        try:
            self.cipher = Fernet(self.key)
        except (ValueError, TypeError):
            # A key that is present but not a Fernet key — `.env` copied from
            # `.env.example`, a truncated paste, a key from another tool. Using
            # it is impossible; silently keeping it means every provider call
            # fails, and switching to a fresh generated key would orphan the
            # secrets already stored. So: report it, then use THIS
            # installation's own key file (the one that already worked, if any).
            logger.error(
                "COGITATE_ENCRYPTION_KEY is set but is not a Fernet key (32 url-safe "
                "base64 bytes). Falling back to the installation's key file."
            )
            key = self._load_or_create_key()
            self.key = key.encode()
            self.cipher = Fernet(self.key)

    @staticmethod
    def key_file_path() -> Path:
        """Where THIS installation keeps its generated key.

        Resolved through `Paths.from_settings`, not the `Paths.data_dir` class
        attribute: the attribute ignores `DATABASE_URL`, so a database pointed
        somewhere else (a sandbox, a script, a second install) would write its
        key into the real install's data dir — and read it back from there.
        """
        from app.core.config import Paths, get_settings

        return Path(Paths.from_settings(get_settings()).data_dir) / KEY_FILE_NAME

    @classmethod
    def _load_or_create_key(cls) -> str:
        """The installation's own key: read it, or generate it once.

        THE FIRST-RUN RULE. A key that changes per process makes every stored
        secret undecryptable, so a random key is not an option; and a key that
        must be pasted into `.env` before the app will start is a first-run wall
        (the app could not even boot to show its own settings page).

        So: one key per install, generated the first time it is needed and kept
        beside the database with owner-only permissions. `COGITATE_ENCRYPTION_KEY`
        still wins when it is set — this is the fallback that makes a bare clone
        work with no configuration at all.
        """
        path = cls.key_file_path()
        try:
            if path.exists():
                existing = path.read_text(encoding="utf-8").strip()
                if existing:
                    return existing
        except OSError as exc:
            logger.error("cannot read the encryption key at %s: %s", path, exc)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            generated = Fernet.generate_key().decode()
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(generated + "\n", encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(path)  # atomic: a crash never leaves half a key
            logger.warning(
                "Generated a new provider-key encryption key at %s. Stored secrets are "
                "tied to it: keep the file with the database, and copy it when you move "
                "an installation.",
                path,
            )
            return generated
        except OSError as exc:
            raise ValueError(
                f"No encryption key configured and none could be created at {path} "
                f"({exc}). Set COGITATE_ENCRYPTION_KEY in .env (a Fernet key), or make "
                f"{path.parent} writable."
            ) from exc
    
    def encrypt(self, api_key: str) -> str:
        """Encrypt API key."""
        return self.cipher.encrypt(api_key.encode()).decode()
    
    def decrypt(self, encrypted_api_key: str) -> str:
        """Decrypt API key."""
        try:
            return self.cipher.decrypt(encrypted_api_key.encode()).decode()
        except FernetInvalidToken:
            logger.error("Invalid encryption token")
            raise ValueError("Invalid API key encryption")


class ProviderService:
    """
    Main provider service that coordinates multiple providers via LiteLLM.
    
    Supports:
    - Multiple LLM providers (Ollama, OpenAI, Anthropic, etc.)
    - Provider fallback on failure
    - API key encryption
    - Usage tracking
    """
    
    # Provider pricing per 1K tokens (approximate, update regularly)
    PRICING = {
        # OpenAI
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        # Anthropic
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
        # Ollama (free, but track anyway)
        "ollama": {"prompt": 0.0, "completion": 0.0},
        # OUR MODELS (2026-08-22, the user: the usage page tracked
        # tokens but cost was always $0.00 — the hardcoded dict lacked
        # our actual brains, so every model fell back to the $0 default.
        # Prices from the OpenRouter catalog dump, per-1K tokens.
        # Free models stay $0 (the token volume still tracks).
        "deepseek/deepseek-v4-flash": {"prompt": 0.000080, "completion": 0.000159},
        "deepseek/deepseek-chat": {"prompt": 0.000080, "completion": 0.000159},
        "deepseek/deepseek-v4-flash-vision-exp": {"prompt": 0.000220, "completion": 0.000660},
        "google/gemini-3.1-flash-lite": {"prompt": 0.000250, "completion": 0.001500},
        "nvidia/nemotron-3-ultra-550b-a55b:free": {"prompt": 0.0, "completion": 0.0},
    }
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize provider service."""
        self.encryption = EncryptionService(encryption_key)
        self._providers_cache: Optional[List[Dict[str, Any]]] = None
    
    def calculate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        pricing: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Calculate cost for API usage.
        
        Args:
            provider: Provider name (openai, anthropic, ollama, etc.)
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            
        Returns:
            Cost in USD
        """
        # Get pricing for model
        # NORMALIZE (2026-08-22, user): the usage logs store prefixed
        # names. Only the OPENROUTER prefix is stripped — the catalog ids
        # under it are bare ('openrouter/nvidia/...' -> 'nvidia/...' which
        # is the PRICING key). The deepseek/ollama prefixes are PART of
        # id ('deepseek/deepseek-v4-flash' is already the key).
        lookup_model = model
        if lookup_model.startswith("openrouter/"):
            lookup_model = lookup_model[len("openrouter/"):]
        # SOURCE ORDER (2026-10-08): a price the caller resolved from the provider's own
        # catalog WINS; PRICING is the fallback, not the source. The built-in table is
        # eleven hand-added entries and drifted from what the providers charge — which is
        # why the usage page showed $0.00 for the model actually in use while its real
        # price sat in `provider_model_cache`, unread.
        if pricing is None:
            pricing = self.PRICING.get(lookup_model)
        if pricing is None:
            # THE HONEST FALLBACK (2026-08-22, user): an unknown model
            # used to silently return $0 (the cost page looked broken).
            # Log the gap so missing pricing is VISIBLE, then fall back.
            #
            # AND SAY WHAT IT MEANS FOR THE LIMIT (D.5, 2026-09-23): a $0
            # measurement is NOT a limit that passed. The cost limit is DECLARED
            # INACTIVE (D8) precisely because a $0 figure cannot be judged against
            # a ceiling — a guard measuring zero is one that does nothing while
            # claiming to. Both halves are in the line on purpose: the pricing gap
            # is WHY, `cost limit inactive` is the CONSEQUENCE, and a reader
            # scanning for spend never mistakes "0.0" for "under the ceiling".
            #
            # NO TAG IN THE LINE ITSELF (2026-09-24): a tag in a STRING is a key
            # handed to someone who may not hold it — this line is read by whoever
            # is looking at the log, not only by us. The ruling the tag stood for is
            # defined in the wiki (`dev-notes/deep-dives/token-limit-policy`,
            # *Appendix — the gate's decisions*), so the comment keeps the pointer
            # and the message keeps the words.
            logger.warning(
                "calculate_cost: no pricing for model=%s — treating as $0; "
                "cost limit inactive (pricing unverified)",
                lookup_model,
            )
            pricing = {"prompt": 0.0, "completion": 0.0}
        
        # Calculate cost
        prompt_cost = (prompt_tokens / 1000) * pricing.get("prompt", 0.0)
        completion_cost = (completion_tokens / 1000) * pricing.get("completion", 0.0)
        
        return round(prompt_cost + completion_cost, 6)
    
    def get_liteLLM_model_name(self, provider: str, model: str) -> str:
        """
        Format model name for LiteLLM.
        
        Args:
            provider: Provider name
            model: Model name
            
        Returns:
            LiteLLM formatted model name (e.g., "openai/gpt-4")
        """
        return f"{provider}/{model}"


class OllamaService:
    """
    Service for Ollama provider business logic.
    
    Handles interactions with Ollama API.
    """

    def __init__(self, base_url: str | None = None):
        """
        Initialize Ollama service.

        Args:
            base_url: the Ollama endpoint — THE ROW's own address, resolved by the caller through
                `provider_endpoints.resolve_endpoint`. There is deliberately no literal default:
                an address the app guessed is not an address anybody chose.
        """
        self.base_url = base_url

    def _endpoint(self, path: str) -> str:
        """The full URL for a path — refusing to dial an address nobody resolved.

        An empty base_url means the caller handed over a row that declares nothing (and a type
        with no canonical endpoint). Building ``"/api/tags"`` off it would be a request to
        nowhere that reads as the provider being down.
        """
        if not self.base_url:
            raise RuntimeError(
                "OllamaService has no endpoint: the provider row declares none and the 'ollama' "
                "type resolves to nothing — set base_url on the row."
            )
        return f"{self.base_url}{path}"

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available Ollama models.

        Returns:
            List of model dictionaries with name, size, family, etc.
        """
        import httpx

        # resolved OUTSIDE the try: an unresolved endpoint is a configuration report, not a
        # fetch failure to be swallowed into an empty list
        url = self._endpoint("/api/tags")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                response.raise_for_status()
                data = response.json()

                models = data.get("models", [])

                # Format models for frontend consumption
                formatted_models = []
                for model in models:
                    formatted_models.append({
                        "name": model.get("name", "unknown"),
                        "size": model.get("size", 0),
                        "size_formatted": self._format_size(model.get("size", 0)),
                        "family": model.get("details", {}).get("family", "unknown"),
                        "format": model.get("details", {}).get("format", "unknown"),
                        "parameter_size": model.get("details", {}).get("parameter_size", "unknown"),
                        "quantization": model.get("details", {}).get("quantization_level", "unknown"),
                        "digest": model.get("digest", ""),
                        "modified_at": model.get("modified_at", ""),
                    })

                logger.info(f"Retrieved {len(formatted_models)} Ollama models")
                return formatted_models

        except httpx.ConnectError as e:
            logger.warning(f"Ollama not available: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching Ollama models: {e}")
            return []

    async def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific model.

        Args:
            model_name: Name of the model

        Returns:
            Model information dictionary or None if not found
        """
        import httpx

        url = self._endpoint("/api/show")  # ditto: refused before the try swallows it

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={"name": model_name},
                    timeout=5.0,
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "name": model_name,
                    "license": data.get("license", ""),
                    "modelfile": data.get("modelfile", ""),
                    "parameters": data.get("parameters", ""),
                    "template": data.get("template", ""),
                    "details": data.get("details", {}),
                    "model_info": data.get("model_info", {}),
                }

        except Exception as e:
            logger.error(f"Error fetching model info for {model_name}: {e}")
            return None

    def _format_size(self, size_bytes: float) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "2.5 GB")
        """
        if size_bytes < 0:
            return "Unknown"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    async def validate_model(self, model_name: str) -> bool:
        """
        Validate that a model exists and is available.

        Args:
            model_name: Name of the model to validate

        Returns:
            True if model exists, False otherwise
        """
        models = await self.list_models()
        return any(m["name"] == model_name for m in models)
