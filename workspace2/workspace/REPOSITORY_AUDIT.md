# Repository Audit

## Safe cleanup targets

- `backend/venv/` — local virtual environment; remove locally before committing.
- `backend/.pytest_cache/`, `**/__pycache__/`, and `*.pyc` — generated Python caches; remove locally before committing.

The execution environment blocked recursive deletion, so these targets remain present but are now covered by `.gitignore`.

## Review required

- `SETUP.md.gz`, `SETUP_unzipped.md`, and `SETUP_unzipped_unzipped.md_gz` duplicate setup material. Keep one authoritative guide (`SETUP.md`) after manual content review.
- `frontend-ui/` is V1 compatibility UI; `frontend-v2/` is the production candidate; `frontend-v2-reference/` is retained reference; `frontend/` and `jarvis_v2_updated/` need ownership review before archival.
- `TEST_REPORT.md` and `USER_GUIDE.md` need freshness review; they were not removed.

## Findings

No source modules, tests, API contracts, or feature systems were removed. Full test execution remains environment-dependent because the local venv was not altered.
