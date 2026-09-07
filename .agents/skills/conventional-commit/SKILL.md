---
name: conventional-commit
description: >-
  Provides guidelines and format templates for generating clean, descriptive git commit messages
  following Conventional Commits standard across backend, frontend, database, and infrastructure.
---

# Conventional Commit Skill

Use this skill to craft clean, standardized git commit messages when modifying files in the repository.

---

## 1. Commit Message Format

```text
<type>(<scope>): <short imperative description>

[optional body providing technical details, context, and motivation]

[optional footer(s) such as Closes #123]
```

---

## 2. Common Types & Scopes

### Types
- `feat`: New feature or user-visible capability.
- `fix`: Bug fix, calculation correction, or error resolution.
- `test`: Adding, updating, or refactoring unit, component, or E2E tests.
- `refactor`: Code change that neither fixes a bug nor adds a feature.
- `perf`: Code change that improves performance.
- `docs`: Documentation, rule, or skill updates.
- `chore`: Build configuration, dependencies, or tooling updates.

### Scopes in Greenline
- `investments`: Portfolio, holdings, transactions, positions, FIFO lots.
- `cashflow`: Inflow/outflow ledger, categories, Sankey diagrams, split payments.
- `accounts`: Bank accounts, demat accounts, customization modals.
- `portfolio`: Backend valuation engine, daily price changes, XIRR calculations.
- `agents`: Agent rules, skills, prompts, and guidelines.
- `ui`: General UI layout, breadcrumbs, theme, navigation.

---

## 3. Mandatory Response Trailer

Whenever repository or workspace files are created, modified, renamed, or deleted during a turn, append the proposed commit message as a dedicated trailing block at the very end of your final response:

```text
Commit Message:
<type>(<scope>): <short imperative description>
```

> **Note**: Omit the commit message for purely conversational responses, planning turns before user approval, and read-only operations (searching, inspecting code, or reading documentation).
