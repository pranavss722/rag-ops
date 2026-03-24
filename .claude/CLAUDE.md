# RAG Pipeline — Development Workflow

## 4-Phase Workflow

Every feature, bugfix, or refactor MUST follow these phases in order.

### Phase 1: Brainstorm
- Discuss the problem space openly with the user.
- Ask clarifying questions — never assume requirements.
- Identify edge cases, constraints, and dependencies.
- Output: shared understanding of WHAT we're solving and WHY.

### Phase 2: Plan
- Produce a concrete implementation plan BEFORE writing code.
- Break work into small, testable increments.
- Identify files to create/modify and their responsibilities.
- Call out risks, trade-offs, and open decisions.
- Get explicit user approval on the plan before proceeding.
- Output: approved plan with clear acceptance criteria.

### Phase 3: TDD (Test-Driven Development)
- Write a failing test FIRST for each increment.
- Implement the minimum code to make the test pass.
- Refactor only after green.
- Cycle: Red -> Green -> Refactor.
- Never skip the red step — if you can't write a failing test, the requirement is unclear.
- Output: passing tests + clean implementation.

### Phase 4: Standards
- Run `ruff check --fix` and `ruff format` on all changed files.
- Ensure no type errors, no security issues (OWASP top 10).
- Verify all tests pass: `pytest -xvs`.
- Review for SOLID / DRY / KISS violations.
- Output: production-ready code that passes CI.

## Rules
- Do NOT write implementation code without a plan approved by the user.
- Do NOT skip TDD — every behavior must have a test.
- Do NOT merge code that fails linting or tests.
- Keep modules small and focused — one responsibility per file.
- All LLM calls must be traced via Langfuse.
- Document architectural decisions in DESIGN.md.
