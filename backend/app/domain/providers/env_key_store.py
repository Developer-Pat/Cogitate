"""
EnvKeyStore — the app's single secrets store.

Decision (2026-08-04): provider API keys live ONLY in .env (gitignored,
file-permission protected). The main DB holds no secrets; the
api_key_encrypted column was removed (DB hygiene round 2, 0057).

This service:
- Maps provider_type → .env variable name (single source of truth)
- Reads/writes the .env file atomically (tmp + rename, 0600 perms)
- Updates the lru_cached settings instance in-place so changes take
  effect immediately (no restart needed)
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

NL = "\n"

# provider_type → .env variable name. Single source of truth for where
# each provider's key lives.
PROVIDER_ENV_VAR: Dict[str, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
    "ollama_cloud": "OLLAMA_CLOUD_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _settings_attr(provider_type: str) -> Optional[str]:
    """provider_type → settings attribute name (openrouter_api_key)."""
    var = PROVIDER_ENV_VAR.get(provider_type)
    return var.lower() if var else None


class EnvKeyStore:
    """Read/write provider API keys in the .env file."""

    def __init__(self, env_path: Optional[Path] = None):
        # .env lives at the project root (settings env_file=".env" resolves
        # relative to CWD = project root). parents[4]: providers(0)/domain(1)/
        # app(2)/backend(3)/project root(4).
        from app.core.config import Paths, get_settings
        self.env_path = env_path or (Paths.from_settings(get_settings()).root / ".env")

    @staticmethod
    def env_var_for(provider_type: str) -> Optional[str]:
        """Get the .env variable name for a provider type."""
        return PROVIDER_ENV_VAR.get(provider_type)

    def get_key(self, provider_type: str) -> Optional[str]:
        """Read the key from the current .env file (fresh read)."""
        var = self.env_var_for(provider_type)
        if not var or not self.env_path.exists():
            return None
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(var + "="):
                return line.split("=", 1)[1].strip() or None
        return None

    def set_key(self, provider_type: str, api_key: str) -> bool:
        """Write/update a provider key in .env (atomic) + update the
        cached settings instance so it takes effect immediately."""
        var = self.env_var_for(provider_type)
        if not var:
            logger.warning("No env var for provider type %s", provider_type)
            return False

        self._write_var(var, api_key)

        attr = _settings_attr(provider_type)
        if attr:
            try:
                from app.core.config import get_settings
                setattr(get_settings(), attr, api_key)
            except Exception as e:
                logger.warning("Failed to update settings.%s: %s", attr, e)

        logger.info("✅ %s written to .env (%s)", var, self.env_path)
        return True

    def clear_key(self, provider_type: str) -> bool:
        """Remove a provider key from .env and clear the settings attr."""
        var = self.env_var_for(provider_type)
        if not var:
            return False

        self._remove_var(var)

        attr = _settings_attr(provider_type)
        if attr:
            try:
                from app.core.config import get_settings
                setattr(get_settings(), attr, "")
            except Exception as e:
                logger.warning("Failed to clear settings.%s: %s", attr, e)

        logger.info("✅ %s removed from .env (%s)", var, self.env_path)
        return True

    # ------------------------------------------------------------------
    # .env file manipulation (atomic)
    # ------------------------------------------------------------------

    def _read_lines(self) -> list:
        if not self.env_path.exists():
            return []
        return self.env_path.read_text(encoding="utf-8").splitlines()

    def _write_var(self, var: str, value: str) -> None:
        lines = self._read_lines()
        new_line = var + "=" + value
        replaced = False
        out = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(var + "="):
                out.append(new_line)
                replaced = True
            else:
                out.append(line)
        if not replaced:
            if out and out[-1].strip() != "":
                out.append("")
            out.append(new_line)
        self._atomic_write(NL.join(out) + NL)

    def _remove_var(self, var: str) -> None:
        lines = self._read_lines()
        out = [line for line in lines if not line.strip().startswith(var + "=")]
        self._atomic_write(NL.join(out) + NL)

    def _atomic_write(self, content: str) -> None:
        """Write via temp file + rename; ensure 0600 perms."""
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.env_path.parent), prefix=".env.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(tmp, 0o600)
            os.replace(tmp, str(self.env_path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        os.chmod(self.env_path, 0o600)


env_key_store = EnvKeyStore()
