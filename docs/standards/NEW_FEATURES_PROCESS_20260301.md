# New Features Process Plan

**Date:** March 1, 2026
**Purpose:** A generic step-by-step generic process for AI agents to implement new features while ensuring robustness, exceptional UX, accurate company data matching, performance, modularity, and scalability.

This plan outlines a sequence of distinct sessions meant to be executed by fresh AI agents. To ensure continuity and context, each agent will read `README.md` and keep shared state in `tmp/new_feature_state.json`.

---

## Session 1: Feature Scoping & Architecture
**Goal:** Define the exact scope of the minimum implementation needed to deliver the highest cost-to-value for the feature. Establish the boundaries for DB, backend, and frontend.
- **Context Establishment:** Read `README.md` and review project structure. Establish the `tmp/new_feature_state.json` file to store progress.
- **Scope Definition:** Determine the necessary additions keeping the implementation minimal. Establish API contracts between the frontend and Python DB layers to allow future framework substitution. Identify out-of-scope follow-up steps to be omitted temporarily and leave a note in the state file.
- **Data Integrity Planning:** Ensure the new feature requires exactly matched and clean data per company. Design the flow.
- **Privacy & Security Planning:** Define required data sanitization, privacy guarantees, anonymization, and expiration rules for any personal data involved.

## Session 2: Backend & Database Implementation
**Goal:** Implement Python backend components, database models, and ingestion modules prioritizing resilience and modularity.
- **Context Check:** Read `README.md` and the `tmp/new_feature_state.json` notes.
- **Implementation:** Create or update API routes, models, and services. Keep imports exclusively at the top of files (none inside methods or classes). Ensure root directory files are not modified unless absolutely necessary.
- **Data & Error Handling:** Ensure all runtime exceptions are safely caught to maintain app stability. Create strict validation checks for inserting clean and precisely matched company data.
- **Security & Privacy:** Apply data sanitization on backend/db layers. Implement retention mechanisms and data expiration if applicable.

## Session 3: Frontend & User Experience
**Goal:** Build a beautiful, modern UI that interacts gracefully with the new API contracts.
- **Context Check:** Read `README.md` and `tmp/new_feature_state.json`.
- **Implementation:** Construct the frontend logic. Adhere strictly to the defined API contracts. Ensure scalable rendering.
- **UX & Robustness:** Implement runtime error handling on the client-side to ensure exceptional User Experience during failures. Add input sanitization for front-end security to prevent XSS.

## Session 4: Testing, Security Verification & Cleanup
**Goal:** Expand test coverage, run verifications, and guarantee clean code structure.
- **Context Check:** Read `README.md` and `tmp/new_feature_state.json`.
- **Testing:** Verify if current test coverage is good and strictly write Pytest E2E/Unit tests covering the feature's core logic, exception handling, data privacy boundaries, and database constraints.
- **Sanity Checks:** Scan for any dead or unused code, ensure all imports are at the top, verify the project root remains clean, and identify any accidentally tracked files that should not be committed to GitHub.

## Session 5: Optimization & Summary Report
**Goal:** Final feature polishing and formulation of future roadmap & improvements.
- **Context Check:** Read `README.md` and `tmp/new_feature_state.json`.
- **Summary Creation:** Retrieve the notes of omitted follow-up steps. Compile a summary proposing next improvements: better UX, performance tuning, enhanced security mechanisms.
- **Optimizations:** Suggest new frameworks, packages, tools, performance upgrades, or Python syntax improvements to consider going forward.
- **Final Cleanup:** Remove `tmp/new_feature_state.json` and any other ad-hoc temp files created during execution. Leave the codebase ready for a final manual test run.
