# Reproduction guide

## Scope

These commands reproduce the installed package and its checks from the public
release. The exact dependency lock is `TESTED_CONSTRAINTS.txt`.

Supported package interpreters are CPython 3.11 and 3.12. The scientific
validation record is CPython 3.12.13; the clean-room closure record is
CPython 3.12.10. Python 3.11 receives CI smoke/core coverage but is not a
replacement for either recorded scientific-validation environment.

## POSIX shells

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --constraint docs/release/TESTED_CONSTRAINTS.txt pip setuptools wheel
python -m pip install --constraint docs/release/TESTED_CONSTRAINTS.txt --no-build-isolation -e '.[dev]'
python scripts/validate_public_release.py
python -m pytest -q
```

## Windows PowerShell

```powershell
python -m venv .venv
$env:PYTHONUTF8='1'; & '.\.venv\Scripts\python.exe' -m pip install --constraint docs\release\TESTED_CONSTRAINTS.txt pip setuptools wheel
$env:PYTHONUTF8='1'; & '.\.venv\Scripts\python.exe' -m pip install --constraint docs\release\TESTED_CONSTRAINTS.txt --no-build-isolation -e '.[dev]'
$env:PYTHONUTF8='1'; & '.\.venv\Scripts\python.exe' scripts\validate_public_release.py
$env:PYTHONUTF8='1'; & '.\.venv\Scripts\python.exe' -m pytest -q
```

The release archive records the source identity of the private immutable G7
candidate in `RELEASE_PROVENANCE.md`. The public validator checks the curated
release's required files, metadata, scientific evidence boundary, and absence
of private-workspace path leakage.
