"""THE A-KEY MACROS SEED (2026-09-03, the akeys roadmap Phase 3).

The out-of-box "A-Key Macros" meta-topic + its 5 starter macro
sets — the A1-A5 action-key bank's default source (the cascade's
step 2: explicit A-default -> this seed -> deactivated).

IDEMPOTENT (startup-safe, the seed_agent_packages pattern): it
creates only what is MISSING (by name / by user_key+topic+name);
it NEVER overwrites user edits. The macro sets are USER DATA once
seeded — the Macros page edits them like any other set, and the
user can point the A-keys at any other meta-topic or edit this
one freely.

The starter content is deliberately MINIMAL (the roadmap decision
6): response macros (Yes / No / Please continue — "those sorts of
things") + the conversational/diagnostic prompts that used to be
hardcoded in MacroKeyboard. Blank slots are fine — the complement
grows through use ("we won't know what to fill in until later").
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import MacroSet, MetaTopic

logger = logging.getLogger(__name__)

AKEYS_META_TOPIC_NAME = "A-Key Macros"

# The 5 mapped sets: A1-A5 (each set's non-empty macros become that
# A-key's flyout items; an empty f-slot is simply absent from the
# flyout — blank keys are fine by design).
AKEYS_SETS = [
    {
        "topic": "Response Macros",
        "name": "Simple responses",
        "description": "The short acknowledgements — Yes, No, Please continue, and the like",
        "sort_order": 0,
        "f1_macro": "Yes",
        "f2_macro": "No",
        "f3_macro": "Please continue.",
        "f4_macro": "Sounds good.",
        "f5_macro": "Understood.",
    },
    {
        "topic": "Greetings & Check-ins",
        "name": "Conversational openers",
        "description": "Opening moves + the are-you-there checks",
        "sort_order": 1,
        "f1_macro": "Hello",
        "f2_macro": "Are you OK?",
        "f3_macro": "Good morning. What is on our agenda?",
        "f4_macro": "Let's wrap up and roll.",
        "f5_macro": None,
    },
    {
        "topic": "Conversation",
        "name": "Conversation management",
        "description": "Continue / cancel / refocus moves",
        "sort_order": 2,
        "f1_macro": "Lets continue working on the previous topic.",
        "f2_macro": "Ignore my previous request.",
        "f3_macro": "Focus on the current task.",
        "f4_macro": "Summarize this conversation so far.",
        "f5_macro": "What have we covered?",
    },
    {
        "topic": "Diagnostics",
        "name": "Diagnostic probes",
        "description": "The state / capability questions",
        "sort_order": 3,
        "f1_macro": "What tools do you have access to?",
        "f2_macro": "Please try that again.",
        "f3_macro": "What model and provider are you configured with?",
        "f4_macro": "What is your context window size?",
        "f5_macro": None,
    },
    {
        "topic": "Modes",
        "name": "Mode switches",
        "description": "The output-mode requests",
        "sort_order": 4,
        "f1_macro": "Switch to concise mode.",
        "f2_macro": "Switch to detailed mode.",
        "f3_macro": "Switch to technical mode.",
        "f4_macro": None,
        "f5_macro": None,
    },
]

# The A1-A5 slot starts (the A-bank maps slot A1 -> the first set,
# etc. — the frontend reads the first 5 mappings in order).
AKEYS_MAPPINGS = [
    {"topic": "Response Macros", "slot_start": "A1"},
    {"topic": "Greetings & Check-ins", "slot_start": "A2"},
    {"topic": "Conversation", "slot_start": "A3"},
    {"topic": "Diagnostics", "slot_start": "A4"},
    {"topic": "Modes", "slot_start": "A5"},
]


async def seed_akeys_macros(db: AsyncSession) -> None:
    """Create the 'A-Key Macros' meta-topic + starter sets (idempotent)."""
    result = await db.execute(
        select(MetaTopic).where(MetaTopic.name == AKEYS_META_TOPIC_NAME)
    )
    meta_topic = result.scalar_one_or_none()

    if meta_topic is None:
        meta_topic = MetaTopic(
            user_key="default",
            namespace="agent",
            name=AKEYS_META_TOPIC_NAME,
            description=(
                "The ACTION-KEY bank — the conversational, diagnostic, and "
                "response macros for the A1-A5 flyouts in the chat input. "
                "Editable: change these macro sets and the A-keys follow."
            ),
            topic_mappings=json.dumps(AKEYS_MAPPINGS),
            is_active=True,
        )
        db.add(meta_topic)
        await db.flush()
        logger.info("Seeded the A-Key Macros meta-topic (id=%s)", meta_topic.id)

    # The macro sets — created only when missing (user_key+topic+name).
    created = 0
    for data in AKEYS_SETS:
        existing = await db.execute(
            select(MacroSet).where(
                MacroSet.user_key == "default",
                MacroSet.topic == data["topic"],
                MacroSet.name == data["name"],
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(
            MacroSet(
                user_key="default",
                namespace="agent",
                topic=data["topic"],
                name=data["name"],
                description=data["description"],
                f1_macro=data["f1_macro"],
                f2_macro=data["f2_macro"],
                f3_macro=data["f3_macro"],
                f4_macro=data["f4_macro"],
                f5_macro=data["f5_macro"],
                is_active=True,
                sort_order=data["sort_order"],
            )
        )
        created += 1

    await db.commit()
    if created:
        logger.info("Seeded %d A-Key Macros starter sets", created)
