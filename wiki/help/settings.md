---
title: Settings & Configuration
category: settings
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
updated: 2026-09-03
tags: [domain/help]
---

# Settings & Configuration

Manage application settings and system configuration.

## Configuration Page
- **Provider Settings** — Add API keys and configure AI services
- **Application Settings** — Theme, language, and display preferences
- **System Configuration** — Pipeline defaults, logging levels

## Key Settings
- **Theme** — Dark/light mode toggle (applied globally)
- **Default Provider** — Primary AI provider for new agents
- **Pipeline Defaults** — Default cognitive profile for new agents

## Title Generation
The title-generation controls (model + auto-title) live on the
[[help/local-services|Local Services]] page — capability config
belongs with the capability, not in user preferences. The rename
buttons (chat + Sessions page) respect the same choice there.

## Tips
- API keys live in the project `.env` (the env-key store), not the
  database.
- Theme preference is persisted in localStorage
