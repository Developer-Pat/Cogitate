---
name: basic-search
description: The way of doing web and knowledge search — the conduct (free and open-source first, ask before paid or API-key tools) and the method (clarify, choose the tool, search, read, fetch, verify, report). Use for ANY lookup or research question.
---

# Basic Search — the way of doing search

This skill governs how you search. It is conduct + methodology: the rules
for what you may use, and the loop you follow for every lookup.

## The conduct

1. **Free and open-source first.** Prefer keyless, free tools
   (duckduckgo, wikipedia, jina_reader, search-knowledge, the internal
   docs). They are the baseline — no setup, no cost, no keys.
2. **Ask before paid sources / API-key tools.** Any search tool or source
   that requires an API key, a paid tier, or a per-call cost is OFF-LIMITS
   until the user approves. Ask BEFORE the first use — not after.
3. **When to ask:**
   - before the first paid or keyed call,
   - before any tool that needs a key you have not been granted,
   - when a free alternative exists but the paid one would be
     materially better (say so, and let the user decide).
4. **When you ask, be specific:** the tool, the key it needs, why the
   free path is insufficient. The user decides; never assume.

## The method (the loop)

For every lookup or research question:

1. **Clarify the question.** What exactly are you looking for? A fact?
   A document? The latest state of something? The question shapes the tool.
2. **Choose the tool:**
   - `duckduckgo` — general web search (facts, news, people, anything web)
   - `wikipedia` — encyclopedic overviews, background, terminology
   - `search-knowledge` — the project's own knowledge base (RAG)
   - `doc-index` / `doc-reader` — the project's documentation
   - `jina_reader` — fetch a SPECIFIC web URL you already have
3. **Search.** Run the best tool first. One query is rarely enough —
   iterate: refine the terms, try the synonyms, check the top results.
4. **Read.** Skim the results before fetching. Prefer primary sources
   (the original page, the official docs, the cited paper) over
   summaries of summaries.
5. **Fetch the promising sources.** Use `jina_reader` on the 1–3 most
   promising URLs. Do not fetch everything — read first, fetch the best.
6. **Verify.** Cross-check important claims against a second source.
   Note the source for every claim you repeat. If the sources disagree,
   say so — do not paper over it.
7. **Report.** Answer with the sources cited. If you found nothing or
   the answer is uncertain, say exactly that — honest gaps beat
   confident guesses.
8. **Format in proper Markdown — NEVER HTML.** No `<br>` (use a
   blank line for the paragraph break), no `<b>`/`<i>` (use
   `**`/`*`), no `•` characters (use `-` or `*` for the lists).
   The answer should render as clean markdown, not HTML tags.

## The loop discipline (the toolkit-tuned rules, 2026-08-24)

The live lessons from running this kit in the real pipeline:

1. **Never repeat a tool call with the same arguments.** After a
   result, either fetch something NEW or produce the answer. A
   repeated identical call is a sign you are stuck — stop and answer
   with what you have.
2. **The progression: search → read → fetch → answer.** One search,
   then read the results, then fetch the 1-3 best, then ANSWER. Do
   not search again after you have fetched — the answer is in the
   pages you have.
3. **The numbers as strings.** The tool arguments arrive as strings —
   `max_results` may be `"5"`, not `5`. The handlers coerce, but the
   discipline: pass small clean values, never exotic types.
4. **Checking a NEW site.** Any public web URL (http/https) is fair
   game — `jina_reader` fetches it (the free reader proxy, no key).
   The recipe: `duckduckgo` to find the sites → `jina_reader` on the
   promising URLs → verify against a second source. New sites are
   not off-limits; the internal doc tools are for the project's own
   knowledge, jina_reader for the web.
5. **The internal reads stay internal.** `search-knowledge`,
   `doc-index`, `doc-reader`, `skill-reader` answer from the
   project's knowledge — they do not reach the web. Use them for
   project questions, jina_reader for the outside world.
6. **Close the loop.** Every turn that used a tool must end with a
   visible answer (or an honest "I could not find it") — never with
   just a tool result.

## The rules of thumb

- **Cost is a feature.** Prefer the free path even when it is slower
  or clumsier. Ask before spending anything.
- **Fetch beats guess.** If a search result looks promising, fetch it —
  do not paraphrase what you think it says.
- **Cite what you used.** Every claim in your answer should trace to a
  source you actually read.
- **Never invent a source.** A real-but-vague answer is better than a
  fabricated citation.
