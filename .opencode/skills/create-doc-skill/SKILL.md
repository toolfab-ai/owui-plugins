---
name: create-doc-skill
description: Use this skill to create a new domain knowledge skill. It involves researching a topic and setting up a structured skill directory with SKILL.md and a references folder.
user-invocable: true
---

# Create Domain Knowledge Skill

This skill guides the agent through the process of creating a new domain-specific skill. This is useful for capturing complex domain knowledge, architectural patterns, or specific library usage that should be available to all agents.

## Table of Contents
- [Approach for Creating Domain Skills](./references/approach.md)
- [Official Skill Specifications](./references/official-specs.md)

## Workflow

1. **Research the Topic**: Use `webfetch`, `grep`, `glob`, and `read` to gather comprehensive information about the target domain or technology.
2. **Initialize Directory**: Create a new directory in `.opencode/skills/<skill-name>`.
3. **Create References**:
    - Create a `.opencode/skills/<skill-name>/references/` directory.
    - Write multiple `.md` files in this directory, each covering a specific sub-topic or aspect of the domain.
    - Each reference file should include:
        - Deep dive into the topic.
        - Code examples if applicable.
        - Links to source material and official documentation.
4. **Create SKILL.md**:
    - Write the main `.opencode/skills/<skill-name>/SKILL.md` file.
    - Include the required frontmatter (`name` and `description`).
    - Provide a **Table of Contents** that links to the files in the `references/` directory.
    - Summarize the core responsibilities and rules for the new skill.

## Structure Template

### SKILL.md Template
```markdown
---
name: <skill-name>
description: <brief-description-for-discovery>
---

# <Skill Title>

<Brief overview of what this skill provides>

## Table of Contents
- [Reference 1](./references/ref1.md)
- [Reference 2](./references/ref2.md)

## Core Principles
- Principle 1
- Principle 2
```

## Best Practices
- **Atomic References**: Keep reference files focused on a single concept.
- **Verifiable Information**: Always include source URLs in the references.
- **Searchable Description**: Ensure the skill description contains keywords that will trigger it appropriately during relevant tasks.
