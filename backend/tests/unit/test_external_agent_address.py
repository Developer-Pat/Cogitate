"""The address an Exa save writes — and the save it must refuse.

The 2026-10-12 ruling (option A): `address_for_client` decides what goes into another process's config,
and a provider nothing can dial is REFUSED rather than written. The page:
`wiki/issues/resolved/embedded-service-literals/exa-model-save-undialable-provider.md`.
"""

import tempfile
from pathlib import Path

import yaml

from app.domain.providers.provider_endpoints import address_for_client, client_can_dial


def test_an_explicit_base_url_wins_even_for_a_provider_nothing_knows():
    """The escape hatch: the caller is the authority about its own process."""
    d = address_for_client(
        "definitely-not-a-provider", client_knows=False, explicit="https://my.proxy/v1"
    )
    assert d.base_url == "https://my.proxy/v1"
    assert d.refusal is None


def test_the_types_canonical_endpoint_beats_the_row_for_a_hybrid_type():
    """`ollama_cloud`'s row carries the NATIVE host; a compat client needs the `/v1` root."""
    d = address_for_client("ollama_cloud", row_type="ollama_cloud", row_base_url="https://ollama.com")
    assert d.base_url == "https://ollama.com/v1"
    # the deviation from the row is REPORTED, never silent
    assert d.note and "row says" in d.note


def test_a_type_the_registry_declines_falls_back_to_the_rows_own_address():
    """`openai` is a hosted vendor AND any self-hosted server, so the row is the decision."""
    d = address_for_client("llama", row_type="openai", row_base_url="http://127.0.0.1:8080/v1")
    assert d.base_url == "http://127.0.0.1:8080/v1"
    assert d.note is None


def test_a_name_that_is_itself_a_registry_type_resolves_without_a_row():
    """The expectation is READ from the registry — the value's home — never copied here.

    (This test carried a literal `…/v1` for one commit: the 2026-10-12 correction moved the
    registry and left the copy behind, which is the drift the dedupe exists to prevent.)
    """
    from app.domain.providers.provider_endpoints import canonical_endpoint

    d = address_for_client("deepseek")

    assert canonical_endpoint("deepseek") is not None
    assert d.base_url == canonical_endpoint("deepseek")


def test_nothing_derivable_but_the_client_knows_it_clears_the_field():
    d = address_for_client("mistral", client_knows=True)
    assert d.clear is True
    assert d.base_url is None
    assert d.refusal is None
    assert d.note  # the operator is told the client's own default applies


def test_nothing_derivable_and_nothing_can_dial_it_refuses():
    d = address_for_client("definitely-not-a-provider", client_knows=False)
    assert d.refusal and "cannot be dialled" in d.refusal
    assert d.base_url is None and d.clear is False


def test_client_can_dial_agrees_with_litellm():
    for known in ("deepseek", "ollama", "mistral", "groq"):
        assert client_can_dial(known) is True, known
    assert client_can_dial("definitely-not-a-provider") is False


def test_the_writer_clears_a_stale_address(monkeypatch):
    """A cleared field is a decision: the previous provider's address must not survive."""
    from app.core import config as cfgmod
    from app.api.v1 import external_agent_router as ear

    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(cfgmod.Paths, "exa_home", tmp)

    ear._write_exa_model_config(
        "deepseek/deepseek-v4-flash", "deepseek", "https://api.deepseek.com", "low"
    )
    written = yaml.safe_load((tmp / "config.yaml").read_text())["model"]
    assert written["base_url"] == "https://api.deepseek.com"

    ear._write_exa_model_config(
        "mistral/mistral-large-latest", "mistral", None, None, clear_base_url=True
    )
    after = yaml.safe_load((tmp / "config.yaml").read_text())["model"]
    assert "base_url" not in after, after
    assert after["provider"] == "mistral"
