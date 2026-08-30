# Project Structure

- `backend/` — FastAPI application, APIs, domain systems, and tests.
- `frontend-v2/` — official production frontend. `npm run build` exports deployable files to `frontend-v2/out/`.
- `legacy/frontend-ui/` — archived Version 1 prototype retained as a backup only; it is not mounted or used during normal execution.
- `frontend-v2-reference/` — superseded V2 prototype retained for reference.
- `frontend/` and `jarvis_v2_updated/` — legacy/review-required artifacts outside the production path.

FastAPI serves `frontend-v2/out/` at `/` after a successful V2 build.
