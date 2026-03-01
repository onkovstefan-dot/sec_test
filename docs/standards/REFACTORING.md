# Generic AI Agent Refactoring Plan

## Goals
- Enhance app robustness, handle runtime exceptions gracefully.
- Ensure clean, exactly matched data reading/insertion per company entity.
- Make the architecture scalable, performant, and resilient.
- Create a modern, beautiful UI for excellent user experience.
- Modularize the application enforcing strict API contracts (Frontend <-> Backend <-> DB) for high framework interchangeability.
- Organize codebase cleanly (`utils`, `modules`, `support`), clean root folder, fix imports.
- Enforce security and data privacy.

## Context Handling & Workflow Guidelines
- The refactoring is split into consecutive, fresh AI agent sessions.
- In each session, the agent must refer to `README.md` to establish project context.
- Intermediate notes between sessions must be saved in the `tmp/` folder (e.g., `tmp/session_X_notes.md`). Subsequent agents must read notes from previous sessions.
- At the end of all sessions, the developer will do one final commit and manually run all `pytest` checks. Do not ask for mid-process verification.

---

## Session 1: Structure & Imports Refactoring
**Objectives:**
1. Read `README.md` to understand context.
2. Ensure imports are fully resolved and located strictly at the top of files (no inline imports in classes/methods).
3. Clean the repository root directory by migrating scattered files.
4. Extract, move, and refactor code into the following structure:
   - `utils/`: Common logic using pure Python features (no DB dependencies).
   - `modules/`: Common business logic and workflows dependent on DB models.
   - `support/`: One-time manual execution scripts or background jobs.
5. Create an intermediate state file at `tmp/session_1_notes.md` containing context and changed behaviors for Session 2.

## Session 2: Robustness, Security, & Privacy
**Objectives:**
1. Read `README.md` and `tmp/session_1_notes.md`.
2. Implement global, graceful exception handling for smooth runtime execution and user experience.
3. Verify data insertion paths: establish strict exact matching schemas for clean data inputs per company.
4. Consider security: implement defensive mechanisms, injection prevention, and specific data sanitization at DB, Backend, and Frontend layers.
5. Consider privacy: enforce sanitization/anonymization for user data. Introduce automated personal data retention rules and expiration jobs.
6. Create an intermediate state file at `tmp/session_2_notes.md` containing context and changed behaviors for Session 3.

## Session 3: Modularity & UI Revamp
**Objectives:**
1. Read `README.md` and all previous notes in `tmp/`.
2. Enforce strict API contracts between Database, Python Backend, and Frontend. Ensure the data transport formats isolate layer dependencies.
3. Audit for scalability, performance, and resilience. Focus on bottlenecks identified in previous layers.
4. Build a beautiful and modern UI to drastically improve the user experience.
5. Create an intermediate state file at `tmp/session_3_notes.md` containing context for the final session.

## Session 4: Code Quality, Cleanup, and Audits
**Objectives:**
1. Read `README.md` and all previous notes in `tmp/`.
2. Check `.gitignore` and ensure no unintended files or credentials are committed to GitHub.
3. Check overall test coverage and build additional pytests to cover uncovered modules (especially newly created structure).
4. Perform global cleanup: verify no dead/unused code is left behind across the whole repository. Ensure a final clean file structure.
5. Generate a comprehensive optimization summary document (suggesting new frameworks, UI tools, libraries, architectural improvements, and syntax enhancements).
6. Remove all temporary execution notes in the `tmp/` directory.
