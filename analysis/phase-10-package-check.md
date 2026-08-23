# Phase 10 — interim package validation

Date: 2026-08-22

The canonical `.venv` was extended with packaging-only tools
`setuptools==84.0.0`, `wheel==0.48.0`, and `build==1.5.0`. The application
runtime remains Python 3.12.13/Tcl-Tk 9.0.4 with `PyUSB==1.3.1`.

Using the last committed source timestamp (`SOURCE_DATE_EPOCH=1787333620`),
two independent wheel builds produced byte-identical artifacts:

```text
infocarry_toolkit-0.1.0-py3-none-any.whl
SHA-256: ffe449d0828564240ee0a57acce4d9f678f871b35a979d5558519f0920c3ad3c
```

The wheel was installed into a temporary Python 3.12 environment with
`PyUSB==1.3.1` supplied, and `infocarry --help` completed successfully. The
entry-point list contains detection, backup, export, inventory, preview, and
desktop commands only; there is no normal write command. No USB device was
accessed.

The standard setuptools source archive was also built, but two identical
builds were not byte-identical even with `SOURCE_DATE_EPOCH`; it is not claimed
as reproducible yet. The wheel is therefore an interim reproducible Python
artifact, not a finished macOS application package.

The repeatable build command is:

```sh
cd ${PROJECT_ROOT}
sh scripts/build_reproducible_wheel.sh /tmp/infocarry-wheel-release
```

The script refuses to overwrite an existing output directory and keeps build
artifacts out of the repository. For the approved limited-audience hobby
release, this reproducible wheel plus the canonical runtime and user guide
satisfies the v0.1 delivery requirement. A signed/notarized `.app` or `.pkg`
and broader macOS support matrix are deferred distribution work; see
`analysis/phase-10-hobby-distribution-decision.md`.
