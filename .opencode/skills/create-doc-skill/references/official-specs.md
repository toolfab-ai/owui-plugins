# Official Skill Specifications

Based on the [Agent Skills Quickstart](https://agentskills.io/skill-creation/quickstart), here are the technical requirements for a skill.

## Required Files
- **SKILL.md**: Must be present in the skill directory.

## Frontmatter Schema
```yaml
---
name: <unique-identifier>
description: <activation-trigger-text>
---
```

- **name**: A short identifier for the skill. Must match the folder name.
- **description**: Tells the agent when to use this skill. Critical for discovery.

## Body Content
The body should contain the instructions the agent follows when the skill is activated. It can include:
- Step-by-step guides.
- Code templates.
- Shell commands to execute.
- Constraints and rules.

## Sources
- [Agent Skills Quickstart](https://agentskills.io/skill-creation/quickstart)
- [Agent Skills Best Practices](https://agentskills.io/skill-creation/best-practices)
- [Agent Skills Specification](https://agentskills.io/specification)
