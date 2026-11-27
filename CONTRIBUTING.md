# Contributing to OfflinePDF

Thanks for helping! Bug reports, ideas, translations and code are all welcome.

## Ground rules

1. **Offline forever.** OfflinePDF must never send files or data anywhere. No telemetry, no update pings, no analytics. Pull requests that add network access will not be merged.
2. **No AGPL/GPL dependencies.** The project is MIT licensed; new dependencies need a permissive license (MIT, BSD, Apache-2.0, MPL-2.0, LGPL for Qt).
3. **Core first.** PDF logic lives in `offlinepdf/core` as plain functions with tests. The GUI and CLI only call into it.

## Development setup

```powershell
git clone https://github.com/demiralpozturk/offline-pdf
cd offline-pdf
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m offlinepdf          # run the app
python -m pytest              # run the tests
```

## Adding a tool

1. Add a function to the right module in `offlinepdf/core` (organize, optimize, convert, overlay, security, metadata).
2. Add tests in `tests/` using the generated sample PDFs from `tests/conftest.py`.
3. Register the tool in `offlinepdf/ui/tools.py` and add its texts to `offlinepdf/i18n.py` in **both** English and Turkish.
4. Optionally expose it in `offlinepdf/cli.py`.

## Translations

All user-facing text is in `offlinepdf/i18n.py`. To add a language, copy the `"en"` block, translate the values and add the language to `LANGUAGES`.

## Pull requests

- Keep PRs focused on one change.
- Make sure `python -m pytest` passes.
- Describe how you tested it.
