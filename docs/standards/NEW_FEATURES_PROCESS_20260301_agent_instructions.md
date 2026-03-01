# AI Agent Execution Instructions for New Features (Date: March 1, 2026)

**Purpose:** Provide simple, copy-and-paste commands to use with fresh AI agents across multiple sessions. This ensures context transfer without loss of focus and enforces robustness, UI improvements, exceptions handling, matched data, and testing.

Use the `NEW_FEATURES_PROCESS_20260301.md` plan to coordinate across these five sequential AI agent sessions. 

---

### Session 1: Feature Scoping & Architecture
**Instructions for the AI Agent:**

```text
You are an AI programming assistant initializing a new feature implementation.
1. Read `README.md` and `docs/standards/NEW_FEATURES_PROCESS_20260301.md` to understand the project architecture and goals.
2. Initialize `tmp/new_feature_state.json` to keep track of decisions, out-of-scope follow-ups, API contracts, and architectural updates. 
3. Scope the new feature with a strict "cost-to-value" approach, keeping implementation minimum. Do not modify existing codebase yet.
4. Establish strict API contracts between the DB, Python backend, and Frontend. Ensure the data required is exactly matched and clean per company.
5. Define security, input sanitization, error handling, and privacy limits (e.g. data retention, anonymization). Log all decisions in `tmp/new_feature_state.json`.
```

---

### Session 2: Backend & Database Implementation
**Instructions for the AI Agent:**

```text
You are an AI programming assistant focused on the backend and database layer for a new feature.
1. Read `README.md`, `docs/standards/NEW_FEATURES_PROCESS_20260301.md`, and `tmp/new_feature_state.json`. 
2. Implement the minimal necessary DB models, ingestion modules, and API route updates while handling runtime exceptions robustly. Make sure all imports are exclusively at the top of the files and that the root folder is left unpolluted.
3. Incorporate strict data matching to enforce clean, per-company data.
4. Add backend data sanitization and defensive mechanisms to validate all inputs and outputs according to our established API contracts. Incorporate data privacy rules, retention, or expiration defined in Session 1 where applicable.
5. Update `tmp/new_feature_state.json` with the files modified and functionality added. 
```

---

### Session 3: Frontend & User Experience
**Instructions for the AI Agent:**

```text
You are an AI programming assistant focusing on the UI and User Experience for the new feature.
1. Read `README.md`, `docs/standards/NEW_FEATURES_PROCESS_20260301.md`, and `tmp/new_feature_state.json`.
2. Construct the frontend logic corresponding to the new API endpoints established in Session 2. Make the UI beautiful, modern, and highly performant. 
3. Implement graceful exception handling on the frontend so runtime errors do not break the UI.
4. Add input validation and frontend security (e.g., XSS prevention, data sanitization before returning to the backend). 
5. Confirm that the API contracts are fully respected, maintaining modularity. Document constraints or issues in `tmp/new_feature_state.json`.
```

---

### Session 4: Testing, Security Verification & Cleanup
**Instructions for the AI Agent:**

```text
You are an AI programming assistant focusing on test coverage, quality assurance, code structure, and security validation.
1. Read `README.md`, `docs/standards/NEW_FEATURES_PROCESS_20260301.md`, and `tmp/new_feature_state.json`.
2. Evaluate if our current test coverage is good. Write comprehensive `pytest` cases (and Playwright where necessary) verifying the new feature core logic, edge cases, error handling, and robust data matching constraints.
3. Review security practices: ensure defensive data sanitization and strict validation are functional on frontend, backend, and DB layers. Verify no sensitive personal data lacks an expiration or anonymization policy.
4. Check for dead/unused code, ensure all imports are ONLY at the top of files, and ensure no unintended files are present (check tracking/commits). Document any omitted features or non-critical bugs found in `tmp/new_feature_state.json`.
```

---

### Session 5: Optimization & Summary Report
**Instructions for the AI Agent:**

```text
You are an AI programming assistant tasked with final optimization and summary.
1. Read `README.md`, `docs/standards/NEW_FEATURES_PROCESS_20260301.md`, and `tmp/new_feature_state.json`.
2. Draft a markdown summary file highlighting the omitted follow-up steps. In that summary, suggest further optimizations such as new frameworks, libraries, syntax improvements, performance tunings, enhanced security techniques, or improved user experience.
3. Review the whole implementation to ensure a clean codebase—remove `tmp/new_feature_state.json` and any other ad-hoc temp tools. 
4. Confirm to the user that testing and cleanup are complete, indicating the project is ready for one final manual run of Pytest and git commit.
```
