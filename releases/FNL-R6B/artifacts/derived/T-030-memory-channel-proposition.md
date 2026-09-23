# T-030 full-record distinguishability and memory-channel proposition

**Task result:** PASS
**Contract:** v0.4
**Evidence basis:** accepted
[V-020 classification and identity map](V-020-equivalence-map.md), with the
exact laws in [T-020](T-020-position-protocols.md) and
[T-021](T-021-nonposition-protocols.md) and the fixed numerical support in
[S-021](S-021-validation-matrix.md). No new calculation is introduced here.

## Definitions and assumptions

Let
\[
\mathcal P=\{P,V,\Theta,PV,P\Theta,V\Theta,PV\Theta\}
\]
be the seven nonempty reset maps, with the common reset rate \(\rho\), inertia
\(M\), activity \(\mathrm{Pe}\), reset targets, nondimensionalization, and
symmetry convention fixed by
[contract v0.4](../../docs/scientific-contract/CONTRACT.md). For
\(X\in\mathcal P\), write \(\mathcal R_2(X;M,\mathrm{Pe},\rho)\) for the full
contract-defined second-order record:

- the component means of \(r,v,u\);
- every component of the raw matrices
  \(R=E[rr^\mathsf T]\), \(S=E[vv^\mathsf T]\),
  \(C=E[rv^\mathsf T]\), \(Q=E[ru^\mathsf T]\),
  \(W=E[vu^\mathsf T]\), and \(U=E[uu^\mathsf T]\);
- the required scalar contractions, centered spatial covariance, stationary
  variance or centered effective diffusion when applicable; and
- the centered and raw spatial-growth classes.

All statements below assume
\[
M>0,\qquad \rho>0,\qquad \mathrm{Pe}\ge 0,
\]
unless a conditional, resonant, or limiting scope is written explicitly.
Means, localization, centered growth, and raw-MSD growth are kept distinct.

## Proposition (full-record distinguishability with an internal memory channel)

For any distinct \(X,Y\in\mathcal P\),
\[
\boxed{\mathcal R_2(X;M,\mathrm{Pe},\rho)
      \ne \mathcal R_2(Y;M,\mathrm{Pe},\rho)}
\]
throughout the stated finite-parameter domain. Moreover, if \(X\) and \(Y\)
differ only by adding position reset while their velocity- and
orientation-reset rules are unchanged, then their complete internal
\((v,u)\) stochastic processes are identical, whereas their spatial records
are distinct. Position reset therefore leaves an exact internal memory
channel while changing long-time motion from transport to localization.

### Exhaustive separating-witness proof

Represent a protocol by its three reset indicators
\((p,v,\theta)\). The 21 unordered pairs are exhausted by the following
disjoint cases.

1. **Different \(p\).** These are the 12 position/non-position pairs. The
   member with \(p=1\) has finite long-time centered spatial variance and
   bounded raw MSD; the member with \(p=0\) has linearly growing centered
   covariance. Thus spatial-growth class is a required-record witness,
   including at \(\mathrm{Pe}=0\).
2. **Same \(p\), different \(\theta\).** At \(\rho>0\), the required
   orientation mean \(\bar u\) and matrix \(U\) differ, independently of
   activity. Either is a component-level witness.
3. **Same \(p\) and \(\theta\), different \(v\).** There are three such
   pairs. For \(P/PV\), both velocity means vanish, but each diagonal
   component of the velocity matrix has the exact positive difference
   \[
   S_{P,ii}-S_{PV,ii}
   =
   \frac{\rho\left[
   M^2\mathrm{Pe}^2\rho+M^2\mathrm{Pe}^2+2M^2\rho+2M^2
   +3M\mathrm{Pe}^2+2M\rho+4M+2\right]}
   {2(M+1)(M\rho+2)(M\rho+M+1)}>0.
   \]
   For \(P\Theta/PV\Theta\) and \(\Theta/V\Theta\),
   \(\bar v\) differs whenever \(\mathrm{Pe}>0\). At the passive endpoint,
   each diagonal velocity component instead differs by
   \[
   S_{\mathrm{no}\ V,ii}-S_{V\ \mathrm{reset},ii}
   =\frac{\rho}{2+M\rho}>0.
   \]
   These witnesses cover the complete stated activity domain rather than
   extrapolating a passive inequality to active parameters.

Every pair enters exactly one case, so special trace coincidences, the passive
endpoint, and resonance surfaces cannot defeat the statement. The proof is
analytic; S-021 validates the exact formula records but is not used to infer
exact inequality from finite numerical comparisons.

## Exact second-order classification

| Protocols | Centered spatial class at \(\rho>0\) | Raw-MSD class |
|---|---|---|
| \(P,PV,P\Theta,PV\Theta\) | stationary/localized | bounded |
| \(V\) | diffusive | diffusive |
| \(\Theta,V\Theta\) | diffusive | ballistic iff \(\mathrm{Pe}\rho>0\), otherwise diffusive |

Hence position reset is necessary and sufficient, within this family, for
finite long-time centered spatial variance. Orientation-only reset can create
nonzero drift and raw ballistic growth without changing the centered
diffusive class.

## Scope-labeled identity ledger and counterexamples to compressed observation

The following exact equalities show that projections of \(\mathcal R_2\) need
not identify the reset map. Each entry includes the witness or boundary that
prevents promotion to full-record equality.

### Sector identity

For all finite physical parameter points,
\[
PV\equiv V,\qquad P\Theta\equiv\Theta,\qquad
PV\Theta\equiv V\Theta
\quad\text{on the full internal }(v,u)\text{ process}.
\]
Equivalently, the internal means, \(S,W,U\), and centered internal blocks
match exactly. This follows because position reset does not enter the
\((v,u)\) generator. The spatial witness is decisive: the left member of each
pair is localized, while the right member has centered diffusive transport
(and, for active \(\Theta\) or \(V\Theta\), raw ballistic growth). No
internal higher-order observable can separate either member of one of these
pairs; any optional contrast must involve the spatial sector.

### Contracted-observable degeneracy

- \(PV/PV\Theta\): the three contractions
  \(\operatorname{Tr}S=E|v|^2\),
  \(\operatorname{Tr}C=E[r\mathbin{\cdot}v]\), and
  \(\operatorname{Tr}R=E|r|^2\) agree exactly for every finite physical
  parameter point. Orientation means and component anisotropy separate the
  records. In the active interior,
  \[
  \operatorname{Tr}\operatorname{Cov}_{PV}(r)
  -\operatorname{Tr}\operatorname{Cov}_{PV\Theta}(r)
  =\frac{\mathrm{Pe}^2}
  {(1+\rho)^2(1+M\rho)^2}>0 .
  \]
  At \(\mathrm{Pe}=0\), \(\bar u\) remains a separating witness.
- \(V/V\Theta\): \(\operatorname{Tr}S\) agrees exactly for every finite
  physical parameter point. At \(\rho>0\), \(\bar u\) separates the records;
  in the active interior, \(V\Theta\) also has nonzero drift and
  \(D_{\mathrm{eff},V}>D_{\mathrm{eff},V\Theta}\).

These are explicit counterexamples to identifying a protocol from the named
scalar contraction(s). They are not counterexamples to the proposition,
because the full component record contains the listed witnesses.

### Resonant identity

For \(P/P\Theta\), the scalar triple
\((\operatorname{Tr}S,\operatorname{Tr}C,\operatorname{Tr}R)\) agrees on the
active resonance \(M\rho=1\), since each difference contains the factor
\(\mathrm{Pe}^2(M\rho-1)\). At the accepted witness point
\(M=\rho=1\), \(\bar u_x=0\) versus \(1/2\),
\(\bar r_x=0\) versus \(3/5\), and centered spatial variance is
\(3.08\) versus \(2.72\).

### Conditional identity

- At \(\mathrm{Pe}=0\), the translational sectors of
  \(P/P\Theta\), \(PV/PV\Theta\), and \(V/V\Theta\) agree; orientation
  outputs still separate each pair for \(\rho>0\).
- On the analytic-only curve
  \[
  \rho=\tfrac12,\qquad
  \mathrm{Pe}^2=
  \frac{27M(M+6)(3M+2)}
       {2(44-9M-80M^2-12M^3)},\qquad
  0<M<0.658170892\ldots,
  \]
  \(V\) and \(\Theta\) have the same diffusion tensor. Their means and raw
  growth classes remain distinct: \(\Theta\) drifts and has ballistic raw
  MSD, while \(V\) does neither. S-021 did not sample this curve, so it is
  retained only as an accepted analytic identity.

### Limiting identity

- As \(M\to0^+\), the position processes of \(P/PV\),
  \(P\Theta/PV\Theta\), and \(\Theta/V\Theta\) coincide. This is singular:
  velocity ceases to be a state, while at every finite \(M>0\) the required
  velocity record separates the pairs.
- At \(\rho=0\), all reset generators vanish and all seven maps reduce to the
  free process. This endpoint lies outside the proposition's positive-rate
  domain.
- Coincident rare- or frequent-reset leading coefficients remain identities
  only of the named asymptotic coefficient; subleading components or the
  spatial-growth witness remain available at every finite positive rate.

## Claim boundary

The proved result is full-record distinguishability together with exact,
scope-labeled information loss under sector restriction, scalar contraction,
special parameter conditions, resonance, or limits. Raw-MSD equality does
not imply centered-covariance equality. Any higher-order or distributional
study is optional and may be described only as an
**optional higher-order/distributional contrast** that adds interpretation
beyond the exact second-order structure.

No conjecture is needed for this proposition or ledger. Novelty and the value
of any optional contrast remain separate literature-dependent judgments.
