# .hestai/ -- Three-Tier Architecture

This folder implements the HestAI three-tier governance architecture for AI coordination.

## Tier Structure

| Tier | Path | Purpose | Git Status |
|------|------|---------|------------|
| **Tier 1** | `.hestai-sys/` | System governance (MCP-delivered, read-only) | Gitignored |
| **Tier 2** | `.hestai/` | Project governance (north-star, decisions, rules) | Committed, PR-controlled |
| **Tier 3** | `.hestai/state/` | Working state (context, reports, sessions) | Gitignored (symlink) |

## What's here? (Tier 2 -- committed governance)

- **north-star/** -- North Star documents and implementation plans
- **decisions/** -- Approved design decision records
- **README.md** -- This file

## Working state (Tier 3 -- via symlink)

`.hestai/state/` is a symlink to the shared `.hestai-state/` directory at the
repository root. This directory is shared across all worktrees and contains:

- **context/** -- Operational state snapshots (PROJECT-CONTEXT, PROJECT-ROADMAP, etc.)
- **reports/** -- Audit trails, investigation reports, stress test results
- **sessions/** -- Session archives
- **research/** -- Research artifacts

The session startup hook creates this symlink automatically in new worktrees.

## Should I commit this?

**Tier 2 (this directory)**: Yes. Contains governance artifacts that define project
identity and approved decisions. Changes require a PR.

**Tier 3 (state/)**: No. Working state is gitignored and shared via symlink.
It changes frequently during sessions and does not require PR review.

## Can I delete it?

If you're not using HestAI **and no one else on your team is**, you can safely
remove this folder. It won't affect your application. Check with your team first.
