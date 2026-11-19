---
title: Diagrams
type: atlas-devnote
category: display-tests
order: 2
confidence: high
updated: 2026-11-18
tags: [type/dev-notes, domain/display-tests]
---

# Diagrams — Numbered Test Blocks

> Report issues by diagram number: "Diagram 2 shows raw code",
> "Diagram 4 is empty".

## Mermaid Flowcharts

**Diagram 1 — simple flowchart (TD).** Should render as a rendered
flowchart, NOT raw code.

```mermaid
flowchart TD
    A[User] --> B[Frontend]
    B --> C[Backend]
    C --> D[Response]
```

**Diagram 2 — flowchart with branches + subgraph.**

```mermaid
flowchart LR
    subgraph FE[Frontend]
        A[Chat UI] --> B[StreamingService]
    end
    subgraph BE[Backend]
        C[chat router] --> D[executor]
    end
    B --> C
    D --> E{success?}
    E -- yes --> F[response]
    E -- no --> G[error]
```

## Sequence Diagrams

**Diagram 3 — sequence diagram.** Participants + message arrows.

```mermaid
sequenceDiagram
    participant U as User
    participant H as useChatStreaming
    participant B as Backend
    U->>H: send message
    H->>B: POST /chat
    B-->>H: event: message
    H->>U: rendered chunk
```

**Diagram 4 — sequence with notes + alt block.**

```mermaid
sequenceDiagram
    participant A as Agent
    participant M as MemoryManager
    A->>M: store turn
    Note over M: compaction check
    alt compact
        M-->>A: compaction triggered
    else normal
        M-->>A: stored
    end
```

## Other Mermaid Types

**Diagram 5 — state diagram.**

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Running: start
    Running --> Idle: stop
    Running --> [*]
```

**Diagram 6 — class diagram.**

```mermaid
classDiagram
    class MemoryManager {
        +recall_facts()
        +extract_facts()
    }
    class KVStoreMemoryManager {
        +_get_conn()
    }
    MemoryManager <|-- KVStoreMemoryManager
```

## HTML / SVG Candidates

> **Decision:** SVG used **sparingly, for special
> diagrams only**. Inline raw HTML/SVG (below) renders as escaped
> text — react-markdown sanitizes it. Standalone `.svg`/`.html`
> files DO render (the wiki API serves them natively). But both
> options are **theme-fixed**: the app has 10 daisyUI themes
> (light/dark/night/dracula/...), mermaid is hardcoded dark, and a
> baked SVG stays dark forever. → Prefer mermaid for everyday
> diagrams (can be made theme-aware); reserve hand-crafted SVG for
> the few hero diagrams where the fixed look is intentional.

**Diagram 7 — inline SVG (expected: escaped text).** Raw HTML/SVG
inside markdown is sanitized by react-markdown — this renders as
literal text by design. It is here as the *negative control*.

**Diagram 8 — image reference.** An `![alt](url)` reference — the
wiki viewer shows the image element (broken-image state until the
file exists):

![cogitate architecture](/wiki/diagrams/cogitate-architecture.svg)

**Diagram 9 — standalone SVG file (candidate).** A real `.svg` file
served by the wiki — this is the "sparingly" path for special
diagrams. (File not created yet — placeholder for the decision.)
