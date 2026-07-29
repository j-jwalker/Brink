---
status: Completed
priority: High
complexity: Low
category: Documentation
tags: [presentation, documentation, collaboration]
blocked_by: []
blocks: []
parent_ticket: null
owner: Andrea
---

# Documentation: share the editable HTML presentation (T105)

## Rationale

The final-project HTML presentation was hosted from a separate local project. Teammates could view
the deployed result but could not edit the source through the shared Brink workflow.

## Summary

Add the complete editable HTML deck under `docs/presentation/html/`, keep its production hosting
identity and credentials out of the repository, and document how teammates can run, edit, test, and
submit presentation changes.

## Scope

### In scope

- Presentation source, styles, screenshots, tests, and local build configuration.
- A practical editing guide covering slide copy, notes, layout, screenshots, validation, and PRs.
- A clear warning that GitHub changes do not automatically publish to the existing hosted URL.

### Out of scope

- Changing the presentation content or visual design.
- Adding an automatic public deployment from GitHub.
- Committing production hosting identifiers, tokens, or other credentials.

## Validation

- [x] `npm install` succeeds from `docs/presentation/html/`.
- [x] `npm test` builds the presentation and passes the rendered-page tests.
- [x] The hosting configuration contains no production project ID or credential.

## Outcome

The team can now edit the presentation through the same branch-and-PR workflow as the rest of Brink.
