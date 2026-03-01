# AI Agent Session Instructions: Maintenance Cycle (March 1, 2026)

*Note: Copy and paste the commands below for each distinct AI agent session to execute the generic plan progressively.*

This document provides ready-to-use prompts for executing the maintenance plan defined in `docs/standards/MAINTENANCE_AND_QUALITY.md`.

---

## External API Call Best Practices Reminder

Before starting any session that involves external API integration, remember these principles:
- **Offload Processing:** Perform filtering, transformation, validation locally in Python
- **Use Database Filtering:** Apply SQL WHERE clauses before making external API calls
- **Batch with ORDER BY:** Use consistent ordering (e.g., `ORDER BY id ASC`) for deterministic, resumable processing
- **Configurable Limits:** Use environment variables (e.g., `SEC_INGEST_DEFAULT_LIMIT=10`, `SEC_INGEST_DEFAULT_WORKERS=1`)
- **Rate Limiting:** Respect external API limits, implement exponential backoff
- **Status Tracking:** Use database status fields (pending/fetched/failed)
- **Validate Metadata:** Check required fields exist before making external calls
- **User Agent Compliance:** Set compliant User-Agent headers (e.g., SEC EDGAR)

---

## Instructions for Session 1

**Prompt:**
```
Read the `README.md` file for architectural constraints and project philosophy.
Read `docs/standards/MAINTENANCE_AND_QUALITY.md` for the overarching refactoring guidelines.
Execute Session 1 of the structural plan:
1. Identify pure logic (no database models) and move it into the `utils/` directory.
2. Identify DB-dependent logic and shift it into the `modules/` directory.
3. Consolidate background/manual scripts into the `support/` directory.
4. Clean the root directory, ensuring only essential configurations are left.
5. Search all python files and hoist all imports to the top of the file.
6. Record your findings, actions, and unresolved structural notes to `tmp/session_notes.txt`.
```

---

## Instructions for Session 2

**Prompt:**
```
Read the `README.md` file for project scope.
Read `docs/standards/MAINTENANCE_AND_QUALITY.md`.
Read previous state from `tmp/session_notes.txt`.
Execute Session 2 focused on Security and Privacy:
1. Identify and remove any untracked, sensitive, or unnecessary files from the workspace that should not be committed to Git.
2. Implement backend, frontend, and DB sanitization and defensive mechanisms across the application.
3. Add data anonymization and user data retention/expiration policies.
4. Append a detailed summary of your security changes and remaining gaps to `tmp/session_notes.txt`.
```

---

## Instructions for Session 3

**Prompt:**
```
Read the `README.md` file.
Read `docs/standards/MAINTENANCE_AND_QUALITY.md`.
Read context from `tmp/session_notes.txt`.
Execute Session 3 for Robustness and Testing:
1. Review the existing test suite and implement missing coverage to ensure comprehensive testing.
2. Refactor parsing and ingestion functions to ensure they only read, insert, and rely on perfectly matched and clean data per entity.
3. Enhance runtime exception handling across endpoints and data pipelines to maintain a seamless user experience.
4. Review all external API calls and ensure they follow the External API Call Best Practices (filtering, batching, configurable limits, status tracking, proper error handling).
5. Verify that jobs respect rate limits and have proper retry mechanisms with exponential backoff.
6. Ensure all external API failures are logged with sufficient context (URL, status code, filing ID, etc.) for debugging.
7. Append an outline of your added tests and fault-tolerance boundaries to `tmp/session_notes.txt`.
```

---

## Instructions for Session 4

**Prompt:**
```
Read the `README.md` file.
Read `docs/standards/MAINTENANCE_AND_QUALITY.md`.
Read context from `tmp/session_notes.txt`.
Execute Session 4 targeting UI/UX and Scalability:
1. Implement a beautiful, modern UI that is scalable and performant.
2. Validate and refactor the modular API contracts bridging the DB, Python backend, and Frontend boundaries, ensuring framework agnosticism.
3. Improve algorithmic efficiency and response times.
4. Write a new section in `tmp/session_notes.txt` suggesting potential future optimizations (new tools, framework swaps, syntax improvements).
```

---

## Instructions for Session 5

**Prompt:**
```
Read the `README.md` file.
Read `docs/standards/MAINTENANCE_AND_QUALITY.md`.
Read context from `tmp/session_notes.txt`.
Execute Session 5 for Final Polish:
1. Conduct a full repository sweep to eliminate all dead, unused, or commented-out code.
2. Ensure no stray configuration files or temporary assets exist.
3. Verify that the previous session notes are completely acted upon.
4. Delete `tmp/session_notes.txt` and any remaining temp state files.
5. Provide a succinct final report indicating that the codebase is ready for manual testing and Git commit.
```
