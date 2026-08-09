# T-011 free inertial active baseline

**Task result:** PASS
**Contract:** v0.3 (locked)
**Model:** free process (`rho=0`) with `r(0)=v(0)=0`, `theta(0)=0`

## Result

The contract-v0.3 free inertial active baseline was solved exactly through the
closed scalar second-moment hierarchy.  The Laplace hierarchy agrees with
Appendix C of Patel and Shee, *Controlling inertial active Brownian motion via
stochastic resetting*, [arXiv:2602.21134v1](https://arxiv.org/abs/2602.21134).
Its long-time velocity limit reproduces the published no-reset result, while
the free position process is diffusive and has no stationary spatial law.

## Assumptions and notation

- Dimensionless contract equations:
  `dr=v dt`, `M dv=-(v-Pe u)dt+sqrt(2)dW`,
  `dtheta=sqrt(2)dW_r`, with `M>0`, `Pe>=0`.
- Translational and rotational Wiener processes are independent.
- `R=<|r|^2>`, `V=<|v|^2>`, `C_rv=<r dot v>`,
  `C_ru=<r dot u>`, and `C_vu=<v dot u>` are raw moments.
- The deterministic initial heading is `u(0)=(1,0)`.  It produces a bounded
  nonzero mean position, so centered spatial variance is
  `R_c=R-|<r>|^2`.  Raw and centered displacement have the same long-time
  slope.
- At `rho=0` all seven protocol generators reduce to the same free generator;
  no protocol-specific reset assumption enters this result.

## Exact closure and Laplace route

With Laplace variable `s`, the zero-initial-state hierarchy is

```text
C_vu~= (Pe/M) / [s (s+1+1/M)]
C_ru~= C_vu~ / (s+1)
V~   = [2 Pe C_vu~/M + 4/(M^2 s)] / (s+2/M)
C_rv~= [V~ + Pe C_ru~/M] / (s+1/M)
R~   = 2 C_rv~ / s.
```

This is the direct transform of

```text
C_vu' = Pe/M - (1+1/M) C_vu
C_ru' = C_vu - C_ru
V'    = -2V/M + 2Pe C_vu/M + 4/M^2
C_rv' = V + Pe C_ru/M - C_rv/M
R'    = 2 C_rv.
```

The `4/M^2` term is the two-dimensional translational-noise contribution.

## Time-domain solution

For `M != 1`,

```text
<u_x> = exp(-t)
<v_x> = Pe [exp(-t)-exp(-t/M)]/(1-M)
<r_x> = Pe [1-M-exp(-t)+M exp(-t/M)]/(1-M)

C_vu = Pe/(M+1) [1-exp(-(M+1)t/M)]
C_ru = Pe/(M+1) [1-(M+1)exp(-t)+M exp(-(M+1)t/M)]

V = 2/M [1-exp(-2t/M)]
  + Pe^2/(M+1) [1+(M+1)exp(-2t/M)/(1-M)
                   -2exp(-(M+1)t/M)/(1-M)].
```

The raw MSD separates into passive and active parts,

```text
R_passive = 4t - 6M + 8M exp(-t/M) - 2M exp(-2t/M)

R_active/Pe^2 = 2t - (3M^2+4M+2)/(M+1)
  - M^2 exp(-2t/M)/(M-1)
  + 2M(2M-1) exp(-t/M)/(M-1)
  + 2M exp(-(M+1)t/M)/[(M-1)(M+1)]
  - 2exp(-t)/(M-1).
```

`C_rv` is exactly `R'/2`.  The apparent `M-1` poles are removable.  The
implementation uses the explicit continuous extension at `M=1`:

```text
<v_x> = Pe t exp(-t)
<r_x> = Pe [1-(1+t)exp(-t)]

V_active/Pe^2 = [1-exp(-2t)]/2 - t exp(-2t)
R_active/Pe^2 = 2t + 2t exp(-t) - t exp(-2t)
                - 9/2 + 6exp(-t) - 3exp(-2t)/2.
```

## Published limit and mandatory reductions

The final-value theorem gives

```text
lim(t->infinity) <|v|^2> = 2/M + Pe^2/(1+M),
```

exactly the no-reset MSV reported in Eq. (5) and Table I of the cited
baseline.  Also,

```text
R_c(t) = (4+2Pe^2)t + O(1),
D_eff = lim R_c/(4t) = 1 + Pe^2/2.
```

Thus position is diffusive, not stationary, while velocity reaches a finite
stationary second moment.

Passive reduction (`Pe=0`):

```text
V = 2/M [1-exp(-2t/M)],
R = 4t - 6M + 8M exp(-t/M) - 2M exp(-2t/M),
V(infinity)=2/M.
```

Singular overdamped position-process limit (`M->0+`, fixed `t>0`):

```text
R -> 4t + 2Pe^2[t-1+exp(-t)],
```

which is the raw MSD of `dr=Pe u dt+sqrt(2)dW`.  At `Pe=0` this further
reduces to `R=4t`.  No finite-inertia velocity formula was evaluated by direct
substitution at `M=0`; velocity is absent from the overdamped state space, as
required by the contract.

## Implementation and validation

- `src/phasemap/theory/free_baseline.py` contains the exact Laplace hierarchy,
  time-domain means and scalar second moments, the explicit `M=1` extension,
  the overdamped position MSD, and `D_eff`.
- `tests/theory/test_free_baseline.py` checks the five Laplace recursions, all
  five time-domain ODE identities, initial data, published stationary MSV,
  passive and overdamped reductions, `M=1` continuity, and centered effective
  diffusion using exact SymPy simplification.
- Command: `.\.venv\Scripts\python.exe -m pytest tests\theory -q`
- Result: **35 passed** (`20.5 s`).
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: **94 passed** (`25.8 s`; count confirmed by `--collect-only`).
- `git diff --check`: **PASS**; only the existing Git LF-to-CRLF advisory for
  `src/phasemap/theory/__init__.py` was emitted.

During the first focused run, one test incorrectly assumed a slots dataclass
had `__dict__`, and two general SymPy limit calls selected ambiguous internal
paths.  The tests were corrected to inspect dataclass fields properly, use the
exact final-value theorem for stationary MSV, and state `t>0` for the singular
overdamped limit.  No derived formula changed and no scientific discrepancy
was observed.

## Limitations

This task establishes the analytic free baseline only.  It does not derive
the complete-reset stationary baseline (T-012), classify partial-reset
protocols, or select a higher-order discriminator.  The web source is a v1
preprint rather than a peer-reviewed final article; the exact formulas were
checked against its displayed Appendix C hierarchy and no-reset result.
