# Skill Creation Approach

This document describes the recommended approach for creating domain knowledge skills within the `.opencode` environment.

## Phase 1: Knowledge Gathering
Before writing any skill files, perform a thorough research phase:
- **Official Docs**: Fetch and summarize official documentation.
- **Codebase Analysis**: If the skill is specific to this project, analyze existing patterns.
- **External Resources**: Use `webfetch` to find best practices and community standards.

## Phase 2: Structural Design
A domain skill should be more than just a single prompt. It should be a knowledge base.
- **SKILL.md**: The entry point. It must be concise but link to everything else.
- **references/**: This is where the bulk of the knowledge lives. By separating it, we keep the main `SKILL.md` small enough for the agent to load quickly during discovery, and only deep-dive into references when needed.

## Phase 3: Drafting and Iteration
1. Start with the `references/` to build up the context.
2. Synthesize the references into the main `SKILL.md`.
3. Test the skill by asking a relevant question and verifying if the agent activates it and follows the instructions.
