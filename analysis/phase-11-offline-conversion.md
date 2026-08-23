# Phase 11 — Offline Conversion Integration

## Scope

This slice establishes the canonical integration boundary for the separate
`${INFOCARRY_TOOLKIT_ROOT}` project. That project has
uncommitted user changes and remains read-only; its duplicate `infocarry`
namespace is not imported or installed into this repository.

The canonical application now owns a small dependency-free offline layer in
`src/infocarry/offline_conversion.py`:

- strict UTF-8 input with the existing CP932/CRLF authoring policy;
- deterministic code-point page wrapping with a 40-column × 20-line logical
  profile for the 240 × 320 device canvas;
- a new-output-only package containing CP932 text, UTF-8 text, logical page
  files, and a JSON manifest;
- a validated uncompressed bottom-up 1-bit Windows BMP serializer for a future
  verified glyph renderer.

The ttk manager exposes **Text Converter**, **Ebook Renderer**, and **Settings
& Help** tabs. The first two are offline-only and cannot claim the device or
invoke the guarded writer. The Ebook Renderer displays logical pages but does
not yet claim font rasterization, EPUB/MOBI parsing, or hardware-compatible
BMP glyph output.

## Safety and namespace boundary

- No live hardware operation was added.
- No existing backup, fixture, capture, or evidence file is modified.
- Conversion output refuses to overwrite an existing destination.
- Unsupported CP932 characters and malformed UTF-8 stop before output.
- The Device Manager's existing-text writer and its authorization gates are
  unchanged.

## Verification

Focused conversion and ttk-summary tests pass, followed by the complete
canonical suite: **226 tests passed** with
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q`.
The result is an offline layout/serialization foundation, not a claim of
EPUB/MOBI or font-rendering compatibility.
