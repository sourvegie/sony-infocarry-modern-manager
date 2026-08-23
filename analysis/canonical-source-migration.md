# Canonical Source Migration

Date: 2026-08-22

## Result

The canonical application source tree is now:

`${PROJECT_ROOT}`

The previous working mirror remains preserved at:

`${LOCAL_PROJECT_MIRROR}/InfoCarry-Toolkit`

The source was copied; it was not moved, renamed, or deleted. The canonical
tree has an initial baseline commit (`e6cd6c9`) and a follow-up fixture
correction (`85b78a9`).

## Included

- `src/` application code
- `tests/` and the two small descriptor/info JSON fixtures
- `analysis/*.md` protocol and format notes
- JSON fixture-report manifests
- the immutable `analysis/phase-8-candidate-1/` ranges required by the
  regression suite
- `AGENTS.md`, `README.md`, `PRODUCT_VISION.md`, `RISK_REGISTER.md`,
  `ROADMAP.md`, and `pyproject.toml`

## Excluded

- `.venv/`, Python caches, `.DS_Store`, and package build metadata
- generated `tests/output/`
- large live-capture and post-write directories (`phase-8-candidate-2` onward,
  `phase-8-live-*`, and `phase-9-export-check-1`)

Those excluded captures remain in the preserved mirror/evidence workspace and
are not needed for ordinary v0.1 development. The candidate-1 exception is
intentional and documented in `AGENTS.md` because one offline regression test
loads its ranges by path.

## Verification

The complete copied source was tested with the existing project environment by
pointing `PYTHONPATH` at the canonical `src/` directory:

```text
Ran 188 tests ... OK
```

The local canonical tree does not contain a virtual environment; create one
locally when packaging or installing dependencies. Original ISO files, device
backups, captures, and hardware state were not modified.
