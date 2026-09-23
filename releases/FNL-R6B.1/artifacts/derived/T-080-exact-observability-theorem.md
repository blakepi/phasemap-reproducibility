# T-080 exact three-observable reset-mask decoder

## Result and scope

Let a nonempty reset map have indicators
\((p,\nu,\eta)\in\{0,1\}^3\) for resetting position, velocity, and
orientation, respectively.  On the matched finite-parameter domain

\[
\mathcal D=\{(M,\mathrm{Pe},\rho):M>0,\ \mathrm{Pe}\geq0,\ \rho>0\},
\]

with the fixed zero reset targets of the scientific contract, define

\[
\Sigma(q)=\left(G(q),\ U_{xx}(q),\ T(q)\right),\qquad
T(q)=\operatorname{Tr}S(q),
\]

where \(G\) is the long-time **centered spatial growth class**.  It is a
tagged asymptotic observable, not a scalar moment.  The result below is exact
at matched parameters; it is not a finite-sample, noisy-data, cross-parameter,
or global-minimality claim.

> **Theorem (exact decoder).**  For every \((M,\mathrm{Pe},\rho)\in
> \mathcal D\), \(\Sigma\) is injective on
> \(\{P,V,\Theta,PV,P\Theta,V\Theta,PV\Theta\}\).  Thus these three
> long-time observables uniquely recover the reset mask.  The theorem does
> not assert that no other two-observable family could be injective.

The full 28-coordinate stationary/asymptotic record remains the accepted
supplementary completeness result.  It is neither needed by this decoder nor
replaced by a claim of process-level equivalence.

## Exact seven-row signature table

Set

\[
\begin{aligned}
A&=\frac{M\mathrm{Pe}^2+2M+2}{M(M+1)},\\
B&=\frac{2(M\mathrm{Pe}^2+2M\rho+2M+2)}
{M(M\rho+2)(M\rho+M+1)},\\
C&=\frac{M^2\mathrm{Pe}^2\rho^2+M\mathrm{Pe}^2\rho+M\mathrm{Pe}^2
+2M\rho^2+4M\rho+2M+2\rho+2}
{M(\rho+1)(M\rho+M+1)}.
\end{aligned}
\]

| Map | \(G\) | \(U_{xx}\) | \(T=\operatorname{Tr}S\) |
|---|---|---:|---:|
| \(P\) | stationary/localized | \(1/2\) | \(A\) |
| \(V\) | diffusive | \(1/2\) | \(B\) |
| \(\Theta\) | diffusive | \((\rho+2)/(\rho+4)\) | \(C\) |
| \(PV\) | stationary/localized | \(1/2\) | \(B\) |
| \(P\Theta\) | stationary/localized | \((\rho+2)/(\rho+4)\) | \(C\) |
| \(V\Theta\) | diffusive | \((\rho+2)/(\rho+4)\) | \(B\) |
| \(PV\Theta\) | stationary/localized | \((\rho+2)/(\rho+4)\) | \(B\) |

The repeated values in a single column are intentional projection-induced
degeneracies; the combined rows are distinct.

## Proof

### 1. The spatial tag recovers \(p\)

For \(p=1\), the exact moment hierarchy is triangular from the orientation
block through the velocity block to the position block.  Its nonconstant
decay rates include \(1\), \(4\), positive inertial rates, and \(\rho\) in
every position block.  Consequently every finite-second-moment initial law
converges to the unique stationary solution, so
\(\operatorname{Cov}(r(t))\) has a finite limit and \(G\) is
stationary/localized.

For \(p=0\), the internal block converges uniquely and
\(\operatorname{Cov}(r(t))=2Dt+O(1)\).  Strictness does not rest on a
numerical table.  Conditional on the Poisson clock and the orientation path,
split velocity and displacement into the independent zero-mean thermal
response and the active response.  Their centered cross covariance vanishes.
The thermal response alone has the exact tensor

\[
D_{\rm th}=\begin{cases}
I,&q=\Theta,\\
\dfrac{2}{(1+M\rho)(2+M\rho)}I,&q=V,V\Theta.
\end{cases}
\]

Both matrices are positive definite on \(\mathcal D\).  The active
conditional covariance is positive semidefinite, so \(D\succeq D_{\rm th}
\succ0\).  Hence all three non-position maps are strictly diffusive in
centered covariance.  Finite initial internal deviations decay and change
only bounded spatial terms; an initial position is removed by centering.
Thus the tag recovers \(p\), independently of the contract's default
initialization.

### 2. \(U_{xx}\) recovers \(\eta\)

On the physical invariant manifold \(\operatorname{Tr}U=1\), the exact
orientation equation is

\[
\dot U=2I-4U+\rho\eta(ee^{\mathsf T}-U).
\]

Its unique long-time value is \(I/2\) for \(\eta=0\), and
\(\operatorname{diag}((\rho+2)/(\rho+4),2/(\rho+4))\) for \(\eta=1\).
Therefore

\[
\frac{\rho+2}{\rho+4}-\frac12=\frac{\rho}{2(\rho+4)}>0,
\]

which recovers \(\eta\) regardless of \(p,\nu,M\), or activity.

### 3. \(\operatorname{Tr}S\) recovers \(\nu\) after \((p,\eta)\)

The only remaining candidate pairs are
\((P,PV)\), \((P\Theta,PV\Theta)\), and \((\Theta,V\Theta)\).
The exact positive trace gaps are

\[
A-B=\frac{\rho N_0}{(M+1)(M\rho+2)(M\rho+M+1)}>0,
\]

\[
C-B=\frac{\rho N_1}{(\rho+1)(M\rho+2)(M\rho+M+1)}>0,
\]

where

\[
\begin{aligned}
N_0={}&M^2\mathrm{Pe}^2\rho+M^2\mathrm{Pe}^2+2M^2\rho+2M^2
+3M\mathrm{Pe}^2+2M\rho+4M+2,\\
N_1={}&M^2\mathrm{Pe}^2\rho^2+3M\mathrm{Pe}^2\rho+M\mathrm{Pe}^2
+2M\rho^2+4M\rho+2M+2\rho+2.
\end{aligned}
\]

All denominators and all displayed numerator monomials are nonnegative on
\(\mathcal D\), while each numerator has a strictly positive constant term.
The first gap separates \(P/PV\); the second separates both
\(P\Theta/PV\Theta\) and \(\Theta/V\Theta\).  Combining the three steps
proves injectivity.

## Complete strict-subsignature map

The following are equality classes at one matched point in \(\mathcal D\).
They are observable-projection equivalences only.  Write

\[
\mathcal E=\{\mathrm{Pe}=0\}\ \cup\ \{M\rho=1\}.
\]

Away from \(\mathcal E\), the classes are:

| Retained coordinates | Equality classes |
|---|---|
| \(G\) | \(\{P,PV,P\Theta,PV\Theta\}\), \(\{V,\Theta,V\Theta\}\) |
| \(U_{xx}\) | \(\{P,V,PV\}\), \(\{\Theta,P\Theta,V\Theta,PV\Theta\}\) |
| \(T\) | \(\{P\}\), \(\{\Theta,P\Theta\}\), \(\{V,PV,V\Theta,PV\Theta\}\) |
| \((G,U_{xx})\) | \(\{P,PV\}\), \(\{P\Theta,PV\Theta\}\), \(\{V\}\), \(\{\Theta,V\Theta\}\) |
| \((G,T)\) | \(\{P\}\), \(\{P\Theta\}\), \(\{PV,PV\Theta\}\), \(\{V,V\Theta\}\), \(\{\Theta\}\) |
| \((U_{xx},T)\) | \(\{P\}\), \(\{V,PV\}\), \(\{\Theta,P\Theta\}\), \(\{V\Theta,PV\Theta\}\) |

On \(\mathcal E\), and only there within \(\mathcal D\),

\[
A-C=-\frac{M\mathrm{Pe}^2\rho(M\rho-1)}
{(M+1)(\rho+1)(M\rho+M+1)}=0.
\]

Thus the \(T\)-only classes become
\(\{P,\Theta,P\Theta\}\) and
\(\{V,PV,V\Theta,PV\Theta\}\), while the \((G,T)\) classes become
\(\{P,P\Theta\}\), \(\{PV,PV\Theta\}\), \(\{V,V\Theta\}\), and
\(\{\Theta\}\).  All other rows of the table are unchanged, because the
orientation coordinate retains its strict gap.  The full three-coordinate
signature remains injective even at \(\mathrm{Pe}=0\) and at \(M\rho=1\).

## Boundary and identity discipline

- \(\rho=0\) is excluded: the jump generator vanishes, the orientation gap
  collapses, and position-reset maps no longer possess a stationary spatial
  law.  This is a true decoder exception, not a removable formula convention.
- \(M=0\) is excluded: it is the singular overdamped position-process limit,
  in which velocity is no longer an independent observable or reset bit.
- Negative parameters, unmatched parameters, changed reset targets, and
  finite-time/noisy observation are outside this theorem.
- \(\mathrm{Pe}=0\) is **not** an exception to the full decoder.  It is only
  a strict-projection degeneracy of \(T\).
- The internal process identities \(PV\equiv_{\rm proc,(v,u)}V\),
  \(P\Theta\equiv_{\rm proc,(v,u)}\Theta\), and
  \(PV\Theta\equiv_{\rm proc,(v,u)}V\Theta\) are sector identities.  They
  do not assert full-process, full-record, or signature equality because
  their spatial tags differ.
- Equalities of a trace or any table class are projection identities.  They
  are not equality of the redundant 28-coordinate frame, and the accepted
  full-record theorem remains supplementary completeness evidence.

## Deterministic implementation evidence

`src/phasemap/theory/observability.py` exposes the exact signature and a
fail-closed decoder.  `tests/theory/test_observability_decoder.py` checks all
seven symbolic rows, both positive kinetic margins, every proper
subsignature class, the passive/resonant trace exceptions, exact decoding at
three numeric points (including the passive endpoint), positive diffusion at
those points, and rejection of \(\rho=0\) or a nonunique input.  No stochastic
producer was run or modified.
