# T-022: all-seven formula registry

**Task result:** PASS

**Contract:** v0.3 (locked)

**Registry schema:** `phasemap.theory.formula_registry` v1.0

## Result

`export_formula_registry(M, Pe, rho)` exports one strict JSON-serializable
record for each accepted reset map in canonical contract order:
`P`, `V`, `Theta`, `PV`, `PTheta`, `VTheta`, and `PVTheta`.

Every record has the same required top-level fields and formula-field order.
`notation` is identical across all records and defines `M`, `Pe`, `rho`,
the shared exact `t`, raw `r_bar=E[r]`, `R=E[rr^T]`, `C=E[rv^T]`, and
`Q=E[ru^T]`, as well as explicit centered `C_centered` and `Q_centered`.
Transport records have `scope=long_time_polynomial` and export the accepted
T-021 polynomial exactly: `r_bar=v_bar*t+b`,
`R=r_bar*r_bar^T+2Dt`, `C=r_bar*v_bar^T+C_centered`,
`Q=r_bar*u_bar^T+Q_centered`, and `Cov_r=2Dt`. Stationary records have the
same raw meanings at `scope=stationary`. Common derived fields are `D_eff`,
`raw_MSD`, `speed`, `r_dot_v`, and `centered_variance`; inapplicable
stationary `D_eff` is JSON `null`. Exact SymPy expressions are serialized
with `srepr`; matrices include explicit shape and Cartesian entries.

The four stationary records delegate directly to the accepted T-020 API;
the three transport records delegate directly to the accepted T-021 API.
No formula was re-derived or changed. Position records retain their `rho>0`
domain; non-position records retain `rho>=0`.

## Regression checks

`tests/theory/test_formula_registry.py` verifies the exact seven-record set,
JSON serializability, shared notation and field order, and field-by-field
equality against every accepted T-020/T-021 API result. This includes raw
versus centered transport moments, the shared `t` polynomial, and the
`Theta` retained-velocity `W` formula through API equality, not a copied
formula.

## Validation

- Focused registry test: `.venv\\Scripts\\python.exe -m pytest tests\\theory\\test_formula_registry.py -q` -> **PASS**, 4 tests.
- Theory suite: `.venv\\Scripts\\python.exe -m pytest tests\\theory -q` -> **PASS**.
- Full suite: `.venv\\Scripts\\python.exe -m pytest -q` -> **PASS**.

## Scope

Only theory exports and regressions were added. No simulation, experiment,
status, contract, or formula source was changed.
