# Generic Application Maintenance and Refactoring Plan

**Date:** March 1, 2026

This document outlines a repeatable, generic process for maintaining high code quality, security, performance, and UI/UX using AI agents. The process is divided into consecutive sessions to ensure robust state management and context handling across completely independent AI agent interactions.

## Context Handling & Execution Rules
- **Reference Material:** Agents must strictly adhere to the project constraints and architecture defined in `README.md`.
- **State Management:** Agents must log their intermediate progress, findings, and context to `tmp/session_notes.txt` at the end of every session. Subsequent sessions must read this file before starting to retain cross-session state.
- **Independence:** This plan avoids referencing the specific implementation details of the codebase, ensuring it remains an executing template that can be run repeatedly over time.
- **Verification:** User will do a final verification, execute pytests, and commit manually at the complete end, avoiding per-session manual checks.

## External API Call Best Practices
When working with external APIs (SEC EDGAR, GLEIF, etc.), always apply these principles to minimize load on external servers and improve reliability:

- **Offload Processing:** Perform all data filtering, transformation, validation, and business logic in Python locally. Never rely on external servers for tasks that can be done client-side.
- **Use Filtering:** Apply database-level filtering (SQL WHERE clauses) before making external API calls. Only fetch what is necessary based on status flags, timestamps, or other criteria.
- **Batch with ORDER BY:** When processing multiple records, use consistent ordering (e.g., `ORDER BY id ASC`) to ensure deterministic, resumable batch processing. This prevents duplicate work if a job is interrupted.
- **Configurable Limits:** Always make batch sizes and concurrency configurable via environment variables (e.g., `SEC_INGEST_DEFAULT_LIMIT`, `SEC_INGEST_DEFAULT_WORKERS`). Start with conservative defaults (limit=10, workers=1) while testing.
- **Rate Limiting Awareness:** Respect external API rate limits. Implement exponential backoff for retries and log rate-limit errors distinctly.
- **Status Tracking:** Use database status fields (e.g., `fetch_status: pending/fetched/failed`) to track processing state. This enables retry logic and prevents redundant API calls.
- **Required Metadata:** Validate that all required fields (URLs, identifiers, etc.) exist before making external calls. Log skipped records clearly with reasons.
- **User Agent Compliance:** Always set compliant User-Agent headers for services that require them (SEC EDGAR requires identification).

---

## Session 1: Structural Refactoring and Clean Dependencies
**Goal:** Modularize the codebase according to defined architectural boundaries and tidy up the project root.
- Read `README.md` for architectural context.
- Identify and move pure Python logic (no DB model dependencies) into the `utils/` folder.
- Identify and move business logic (requiring DB models) into the `modules/` folder.
- Identify and move one-off, manual, or background job scripts into the `support/` folder.
- Ensure the root directory remains as clean as possible.
- Scan all files and move all imports to the top of each file (remove inline/method-level imports).
- Write a summary of structural changes into `tmp/session_notes.txt`.

## Session 2: Security, Data Privacy, and Git Hygiene
**Goal:** Fortify the application against vulnerabilities, ensure privacy compliance, and clean up repository artifacts.
- Read `README.md` and `tmp/session_notes.txt`.
- Check the workspace for files that should not be committed to GitHub and update `.gitignore` accordingly.
- Implement defensive programming mechanisms, input validation, and data sanitization across all layers (Frontend, API/Backend, Database).
- Implement data privacy controls (anonymization, sanitization).
- Enforce data retention and expiration mechanisms for any personal or sensitive records.
- Append specifics of the applied security mechanisms to `tmp/session_notes.txt`.

## Session 3: Robustness, Exception Handling, and Testing
**Goal:** Enhance runtime stability, data integrity, and test coverage.
- Read `README.md` and `tmp/session_notes.txt`.
- Analyze current test coverage. Write new tests to ensure comprehensive coverage.
- Implement comprehensive exception handling at runtime to guarantee a graceful user experience during errors.
- Ensure data ingestion pipelines read, insert, and rely on clean, exactly matched data per entity payload.
- **External API Integration:** Review all external API calls and ensure they follow the External API Call Best Practices (filtering, batching, configurable limits, status tracking, proper error handling).
- Verify that jobs respect rate limits and have proper retry mechanisms with exponential backoff.
- Ensure all external API failures are logged with sufficient context (URL, status code, filing ID, etc.) for debugging.
- Append a report of the testing coverage and fault-tolerance improvements to `tmp/session_notes.txt`.

## Session 4: Scalability, UI/UX, and Modernization
**Goal:** Ensure the application scales, looks great, and remains framework-agnostic.
- Read `README.md` and `tmp/session_notes.txt`.
- Enhance the UI/UX to be beautiful, modern, and user-friendly.
- Ensure strict adherence to modular API contracts between the Database, Python backend, and the Frontend to allow for easy framework switching in the future.
- Review and refactor code to ensure scalability, performance, and resilience under load.
- Create a summary block inside `tmp/session_notes.txt` with suggested project optimizations (new frameworks, libraries, packages, performance tools, syntax improvements).

## Session 5: Dead Code Elimination and Final Polish
**Goal:** Perform final cleanups, remove leftover artifacts, and finalize the maintenance cycle.
- Read `README.md` and `tmp/session_notes.txt`.
- Identify and remove all dead, commented-out, or unused code.
- Ensure the overall structure is clean and adheres to the plan.
- Delete the temporary context file (`tmp/session_notes.txt`) and any other intermediate artifacts inside `/tmp/`.
- Output a final readiness confirmation for the manual test run and commit.
