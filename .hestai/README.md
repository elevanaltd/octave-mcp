# .hestai/

This folder is used for AI coordination and context management. It does not affect your application code and can be safely ignored if you're not using the HestAI system.

## What's here?

- **context/** - Operational state snapshots for AI agents
- **workflow/** - Phase tracking and methodology documents
- **reports/** - Audit trails and evidence artifacts
- **sessions/** - Session archives (when present)

## Should I commit this?

Yes. The `.hestai/` folder should be committed to git. It contains coordination artifacts that help AI agents understand project context across sessions.

## Can I delete it?

If you're not using HestAI **and no one else on your team is using it**, you can safely remove this folder. It won't affect your application. Check with your team first.
