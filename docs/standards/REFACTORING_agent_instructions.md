# AI Agent Instructions for Refactoring Plan

Execute the following independent sessions. Start each session strictly with the content provided. Before beginning, make a fresh workspace read of `README.md` to establish accurate context. You must save progress notes in `tmp/` so subsequent sessions can inherit them. 

---

## Session 1: Structure & Imports Refactoring
**Copy & Paste Prompt:**
"""
You are an AI programming assistant executing Session 1 of our refactoring plan.
Please perform the following steps carefully without breaking the existing functionality:
1. Read `README.md` to understand context.
2. Ensure imports are fully resolved and located strictly at the top of files (no inline imports in classes/methods).
3. Clean the repository root directory by migrating scattered files. Ensure files not meant to be in root are relocated appropriately.
4. Extract, move, and refactor code into the following structure:
   - `utils/`: Common logic using pure Python features (no DB dependencies).
   - `modules/`: Common business logic and workflows dependent on DB models.
   - `support/`: One-time manual execution scripts or background jobs.
5. Create an intermediate state file at `tmp/session_1_notes.md` containing context and changed behaviors.
Do not ask for verification. I will perform manual testing at the end of all sessions.
"""

---

## Session 2: Robustness, Security, & Privacy
**Copy & Paste Prompt:**
"""
You are an AI programming assistant executing Session 2 of our refactoring plan.
Please perform the following steps carefully without breaking the existing functionality:
1. Read `README.md` and `tmp/session_1_notes.md`.
2. Implement global, graceful exception handling for smooth runtime execution and user experience.
3. Verify data insertion paths: establish strict exact matching schemas for clean data inputs per company.
4. Consider security: implement defensive mechanisms, injection prevention, and specific data sanitization at DB, Backend, and Frontend layers.
5. Consider privacy: enforce sanitization/anonymization for user data. Introduce automated personal data retention rules and expiration jobs.
6. Create an intermediate state file at `tmp/session_2_notes.md` containing context and changed behaviors.
Do not ask for verification. I will perform manual testing at the end of all sessions.
"""

---

## Session 3: Modularity & UI Revamp
**Copy & Paste Prompt:**
"""
You are an AI programming assistant executing Session 3 of our refactoring plan.
Please perform the following steps carefully without breaking the existing functionality:
1. Read `README.md` and all previous notes in `tmp/`.
2. Enforce strict API contracts between Database, Python Backend, and Frontend. Ensure the data transport formats isolate layer dependencies.
3. Audit for scalability, performance, and resilience. Focus on bottlenecks identified in previous layers.
4. Build a beautiful and modern UI to drastically improve the user experience.
5. Create an intermediate state file at `tmp/session_3_notes.md` containing context and changed behaviors.
Do not ask for verification. I will perform manual testing at the end of all sessions.
"""

---

## Session 4: Code Quality, Cleanup, and Audits
**Copy & Paste Prompt:**
"""
You are an AI programming assistant executing Session 4 of our refactoring plan.
Please perform the following steps carefully without breaking the existing functionality:
1. Read `README.md` and all previous notes in `tmp/`.
2. Check `.gitignore` and ensure no unintended files or credentials are committed to GitHub.
3. Check overall test coverage and build additional pytests to cover uncovered modules (especially newly created structure).
4. Perform global cleanup: verify no dead/unused code is left behind across the whole repository. Ensure a final clean file structure.
5. Generate a comprehensive optimization summary document (suggesting new frameworks, UI tools, libraries, architectural improvements, and syntax enhancements).
6. Remove all temporary execution notes in the `tmp/` directory.
Do not ask for verification. I will perform manual testing at the end of all sessions.
"""
