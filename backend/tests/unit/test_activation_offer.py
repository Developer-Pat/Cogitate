"""Exa's model: OFFERED from this install's chat answer, never inherited silently.

The rule the code quotes ("a model is exactly the kind of silent decision this project
refuses") is about silence, not about the same model — so a fresh install that has already
resolved a chat model offers it to Exa, and only an explicit accept writes it.

What these defend:

- no chat model → no offer, and the fix still names the explicit flags;
- a chat model → the offer is reported (not written) and the fix names `--from-default`;
- `--from-default` (the accept) writes Exa's model section, and the probe then reads it back;
- an explicit --model/--provider still wins, because an offer is not a restriction.
"""

from sqlalchemy import delete

from app.domain.external_agent import activation
from app.infrastructure.database.models import Agent, Capability, Provider


async def _bare(db) -> None:
    """Name the starting state — the test database is shared between runs."""
    for model in (Agent, Provider, Capability):
        await db.execute(delete(model))
    await db.commit()


def _chat_row() -> Provider:
    return Provider(
        name="llama",
        display_name="Llama",
        provider_type="llama",
        base_url="http://localhost:11434",
        is_active=True,
        is_default=True,
        config={"default_model": "llama3.2"},
    )


async def test_no_chat_model_means_no_offer(test_session, tmp_path):
    await _bare(test_session)
    report = await activation.probe(test_session, home=tmp_path / "exa-home")
    assert report.offer is None
    model_check = next(c for c in report.checks if c.name == "model")
    assert not model_check.ok
    assert "--model/--provider" in model_check.fix


async def test_a_resolved_chat_model_is_offered_and_named_in_the_fix(test_session, tmp_path):
    await _bare(test_session)
    test_session.add(_chat_row())
    await test_session.commit()

    report = await activation.probe(test_session, home=tmp_path / "exa-home")
    assert report.offer is not None
    assert report.offer.provider == "llama"
    assert report.offer.model, "the offer carries the row's own model string"
    model_check = next(c for c in report.checks if c.name == "model")
    assert not model_check.ok, "nothing is set for you — the offer is still an offer"
    assert "--from-default" in model_check.fix
    assert report.offer.model in model_check.fix


async def test_the_offer_names_the_type_not_the_rows_capitalised_name(test_session, tmp_path):
    """Measured on the install (2026-11-20): a row NAMED "Deepseek" typed "deepseek" offered
    `Deepseek/deepseek-flash` — litellm's handlers are lowercase, so that string dials nothing.
    The offer must carry the type's handler."""
    await _bare(test_session)
    test_session.add(
        Provider(
            name="Deepseek",
            display_name="Deepseek",
            provider_type="deepseek",
            base_url="https://api.deepseek.com",
            is_active=True,
            is_default=True,
            config={"default_model": "deepseek-flash"},
        )
    )
    await test_session.commit()

    offer = await activation.chat_offer(test_session)
    assert offer is not None
    assert offer.model == "deepseek/deepseek-flash", offer.model


async def test_from_default_accepts_the_offer_and_writes_the_section(test_session, tmp_path):
    await _bare(test_session)
    test_session.add(_chat_row())
    await test_session.commit()
    home = tmp_path / "exa-home"

    report, log = await activation.apply(test_session, home=home, from_default=True)

    written = activation.read_model_config(home)
    assert written["provider"] == "llama"
    assert written["model"], "the accepted offer is what lands in config.yaml"
    assert any("offered by this install and accepted" in line for line in log)
    model_check = next(c for c in report.checks if c.name == "model")
    assert model_check.ok, "the probe reads back what the accept wrote"
