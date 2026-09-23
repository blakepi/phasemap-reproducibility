# Reproduction guide

## Scope

These commands reproduce the installed package and its smoke/core checks.
They do not publish, submit, register a DOI, or establish a public release.
The exact dependency lock is `TESTED_CONSTRAINTS.txt`.

Supported package interpreters are CPython 3.11 and 3.12. The scientific
validation record is CPython 3.12.13; the clean-room closure record is
CPython 3.12.10. Python 3.11 receives CI smoke/core coverage but is not a
replacement for either recorded scientific-validation environment.
The September 2026 FNL preparation additionally uses a fresh CPython 3.12.14
environment with the same locked dependency versions; the earlier records
above remain historical records, not claims about the current interpreter.
The constraint file selects NumPy 2.4.6 on Python 3.11 and NumPy 2.5.1 on
Python 3.12 so both declared interpreter branches remain exactly installable.
The S-074 development tests additionally require SciPy for deterministic
matrix-exponential horizon checks. The current constraints select
[SciPy 1.16.3](https://pypi.org/project/scipy/1.16.3/) on Python 3.11 and
[SciPy 1.17.1](https://pypi.org/project/scipy/1.17.1/) on Python 3.12;
this addition does not retroactively change the historical environments.

## POSIX shells

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --constraint docs/release/TESTED_CONSTRAINTS.txt pip setuptools wheel
python -m pip install --constraint docs/release/TESTED_CONSTRAINTS.txt --no-build-isolation -e '.[dev]'
python -m pytest -q tests/simulation/test_simulator_smoke.py tests/theory tests/integration/test_validation_registry.py tests/integration/test_g7_publication_contract.py
```

## Windows PowerShell

```powershell
python -m venv .venv
$env:PYTHONUTF8='1'; & '.\.venv\Scripts\python.exe' -m pip install --constraint docs\release\TESTED_CONSTRAINTS.txt pip setuptools wheel
$env:PYTHONUTF8='1'; & '.\.venv\Scripts\python.exe' -m pip install --constraint docs\release\TESTED_CONSTRAINTS.txt --no-build-isolation -e '.[dev]'
$env:PYTHONUTF8='1'; & '.\.venv\Scripts\python.exe' -m pytest -q tests\simulation\test_simulator_smoke.py tests\theory tests\integration\test_validation_registry.py tests\integration\test_g7_publication_contract.py
```

For a frozen release candidate only, start in a pristine Git checkout and run
`python scripts/verify_release_blobs.py` before installing dependencies. That
verifier checks the manifest's pinned source identity, not this mutable
working-tree revision.

For a standalone successor archive and deterministic manuscript-PDF QA, see
[PORTABLE_PUBLICATION_ARCHIVE.md](PORTABLE_PUBLICATION_ARCHIVE.md).
