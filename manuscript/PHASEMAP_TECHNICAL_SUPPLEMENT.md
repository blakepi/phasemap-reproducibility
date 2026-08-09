# Technical Supplement: Exact Generator, Second-Order Closure, and Seven-Map Distinguishability

This supplement gives the generator, closed second-order hierarchy, exhaustive
pairwise proof, restricted-identity ledger, and mandatory limits for the
two-dimensional inertial active Brownian particle with deterministic Poisson
resetting. It is written to be read independently. Repository links are
included only as traceability pointers to the accepted symbolic records and
implementations.

## S1. Model, reset semantics, and generator

Let \(r=(x,y)^\mathsf T\), \(v=(v_x,v_y)^\mathsf T\), and
\(u(\theta)=(\cos\theta,\sin\theta)^\mathsf T\). Between resets,

\[
dr=v\,dt,\qquad
M\,dv=-(v-\mathrm{Pe}\,u)\,dt+\sqrt{2}\,dW_t,\qquad
d\theta=\sqrt{2}\,dW_{r,t},
\]

where \(W_t\) is a standard two-component Wiener process,
\(W_{r,t}\) is an independent scalar Wiener process, and

\[
M>0,\qquad \mathrm{Pe}\ge 0,\qquad \rho\ge 0.
\]

Reset times are those of an independent Poisson process of rate \(\rho\).
Each reset is instantaneous. With \(0\) denoting the appropriate scalar or
two-component zero, the seven nonempty deterministic maps are

| Protocol \(q\) | Full post-reset state \(R_q(r,v,\theta)\) |
|---|---|
| \(P\) | \((0,v,\theta)\) |
| \(V\) | \((r,0,\theta)\) |
| \(\Theta\) | \((r,v,0)\) |
| \(PV\) | \((0,0,\theta)\) |
| \(P\Theta\) | \((0,v,0)\) |
| \(V\Theta\) | \((r,0,0)\) |
| \(PV\Theta\) | \((0,0,0)\) |

Every unlisted state variable is retained exactly. For a smooth observable
\(f(r,v,\theta)\), the backward generator is

\[
\boxed{
\begin{aligned}
\mathcal L_q f
={}&v\mathbin{\cdot}\nabla_r f
-\frac{v-\mathrm{Pe}\,u}{M}\mathbin{\cdot}\nabla_v f
+\frac{1}{M^2}\Delta_v f+\partial_\theta^2 f\\
&+\rho\left[f(R_q(r,v,\theta))-f(r,v,\theta)\right].
\end{aligned}}
\]

The common default initial state is
\(r(0)=0\), \(v(0)=0\), and \(\theta(0)=0\). Thus
\(\bar r(0)=\bar v(0)=0\), \(\bar u(0)=e=(1,0)^\mathsf T\),
all raw second moments containing \(r\) or \(v\) initially vanish, and
\(U(0)=ee^\mathsf T\).

Traceability:
[scientific contract](../docs/scientific-contract/CONTRACT.md) and
[symbolic generator implementation](../src/phasemap/theory/generator.py).

## S2. Temporal scope of the second-order record

For a protocol \(q\), define

\[
\mathcal R_2(q;M,\mathrm{Pe},\rho)
\]

to be the fixed stationary-or-asymptotic component-level output used by the
classification. For a position-reset map, the record contains the stationary
long-time limits of all means and raw second moments below, the centered
spatial covariance, and the finite stationary variance. For a map without
position reset, the record contains the stationary internal \((v,u)\) moments
and the accepted long-time spatial polynomial coefficients:
\(\bar r(t)=\bar v\,t+b+o(1)\),
\(\operatorname{Cov}r(t)=2Dt+O(1)\), the corresponding raw \(R,C,Q\)
coefficients, \(D_{\mathrm{eff}}\), and the centered and raw spatial-growth
classes. Equality means equality of every applicable stationary value and
every applicable long-time coefficient at matched
\((M,\mathrm{Pe},\rho)\). The theorem does not assert equality or
distinguishability of unspecified finite-time transients, and it does not
claim finite-sample recoverability.

The raw matrices used throughout are

\[
\begin{gathered}
R=E[rr^\mathsf T],\quad S=E[vv^\mathsf T],\quad
C=E[rv^\mathsf T],\\
Q=E[ru^\mathsf T],\quad W=E[vu^\mathsf T],\quad
U=E[uu^\mathsf T],
\end{gathered}
\]

with means \(\bar r=E[r]\), \(\bar v=E[v]\), and
\(\bar u=E[u]\). The required named scalar contractions are

\[
\mathrm{TrR}:=\operatorname{Tr}R=E|r|^2,\qquad
\mathrm{TrS}:=\operatorname{Tr}S=E|v|^2,\qquad
\mathrm{TrC}:=\operatorname{Tr}C=E[r\mathbin{\cdot}v].
\]

The centered spatial covariance is
\(\operatorname{Cov}(r)=R-\bar r\bar r^\mathsf T\). For a diffusive
protocol,

\[
D_{\mathrm{eff}}
=\lim_{t\to\infty}\frac{\operatorname{Tr}\operatorname{Cov}(r(t))}{4t}.
\]

## S3. Ordered redundant 28-coordinate frame and exact linear moment hierarchy

The implementation stores the ordered coordinate frame

\[
\begin{aligned}
\mathcal F_2=\big(&1;\\
&r_x,r_y;\\
&v_x,v_y;\\
&u_x,u_y;\\
&R_{xx},R_{xy},R_{yy};\\
&S_{xx},S_{xy},S_{yy};\\
&C_{xx},C_{xy},C_{yx},C_{yy};\\
&Q_{xx},Q_{xy},Q_{yx},Q_{yy};\\
&W_{xx},W_{xy},W_{yx},W_{yy};\\
&U_{xx},U_{xy},U_{yy}\big).
\end{aligned}
\]

These are 28 stored coordinates, not an unrestricted 28-element basis.
Every physical moment record lies on the invariant manifold

\[
\boxed{\texttt{one}=1,\qquad
\operatorname{Tr}U=U_{xx}+U_{yy}=1,}
\]

or, in homogeneous coordinate form,
\(\texttt{one}-U_{xx}-U_{yy}=0\). The symmetric matrices \(R,S,U\)
retain three stored components, while the nonsymmetric matrices \(C,Q,W\)
retain all four. Together with the constant and six first moments, the
implementation inventory is \(1+6+9+12=28\) entries. The exact trace
constraint makes this inventory a redundant moment frame. Retaining it
keeps the accepted generator, formula, and serialization interfaces stable.

In implementation-stable names, the same exact order is

```text
one,
r_x, r_y,
v_x, v_y,
u_x, u_y,
rr_xx, rr_xy, rr_yy,
vv_xx, vv_xy, vv_yy,
rv_xx, rv_xy, rv_yx, rv_yy,
ru_xx, ru_xy, ru_yx, ru_yy,
vu_xx, vu_xy, vu_yx, vu_yy,
uu_xx, uu_xy, uu_yy
```

Here `rr`, `vv`, `rv`, `ru`, `vu`, and `uu` denote
\(R,S,C,Q,W,U\), respectively.

Write the reset indicators of protocol \(q\) as
\((p,\nu,\eta)\in\{0,1\}^3\), for position, velocity, and orientation reset,
respectively. For binary indicators, write
\(a\vee b=a+b-ab\). Direct application of \(\mathcal L_q\) gives the exact
closed hierarchy

\[
\dot 1=0,
\]

\[
\begin{aligned}
\dot{\bar u}
&=-\bar u+\rho\eta(e-\bar u),\\
\dot U
&=2\operatorname{Tr}(U)I-4U+\rho\eta(ee^\mathsf T-U),
\end{aligned}
\]

This trace form is the exact coordinate representation used by the
28-component closure:
\(\dot U_{xx}=-2U_{xx}+2U_{yy}+\rho\eta(1-U_{xx})\),
\(\dot U_{xy}=-(4+\rho\eta)U_{xy}\), and
\(\dot U_{yy}=2U_{xx}-2U_{yy}-\rho\eta U_{yy}\).
The physical invariant \(\operatorname{Tr}U=1\) then also permits the
equivalent shorthand \(2I-4U\) on admissible states.
Indeed, taking the trace gives

\[
\frac{d}{dt}\big(\operatorname{Tr}U-1\big)
=-\rho\eta\big(\operatorname{Tr}U-1\big).
\]

Protocols without orientation reset (\(\eta=0\)) preserve the trace
constraint, while protocols with orientation reset (\(\eta=1\)) restore
any trace deviation exponentially at rate \(\rho\). Thus every one of the
seven generators leaves the physical invariant manifold unchanged.
The generator's explicit physical-state validation entry point rejects states
outside this manifold rather than assigning them a physical interpretation.

\[
\begin{aligned}
\dot{\bar v}
&=-\frac{\bar v-\mathrm{Pe}\,\bar u}{M}-\rho\nu\bar v,\\
\dot W
&=\frac{\mathrm{Pe}}{M}U-\left(1+\frac1M\right)W
-\rho(\nu\vee\eta)W
+\rho\eta(1-\nu)\bar v e^\mathsf T,\\
\dot S
&=-\frac{2}{M}S+\frac{\mathrm{Pe}}{M}(W+W^\mathsf T)
+\frac{2}{M^2}I-\rho\nu S,
\end{aligned}
\]

and

\[
\begin{aligned}
\dot{\bar r}
&=\bar v-\rho p\bar r,\\
\dot Q
&=W-Q-\rho(p\vee\eta)Q
+\rho\eta(1-p)\bar r e^\mathsf T,\\
\dot C
&=S-\frac1M C+\frac{\mathrm{Pe}}{M}Q
-\rho(p\vee\nu)C,\\
\dot R
&=C+C^\mathsf T-\rho pR.
\end{aligned}
\]

These tensor equations are precisely the component equations
\(\dot m_q=A_qm_q\) in the ordered frame \(\mathcal F_2\). The constant
entry carries the affine terms. No moment outside \(\mathcal F_2\) is
generated. Any uniqueness statement for this coordinate system is restricted
to the physical invariant manifold above; no unrestricted ambient-space
uniqueness is claimed.

### S3.1 Long-time solution for position-reset protocols

For \(P,PV,P\Theta,PV\Theta\) with \(\rho>0\), every position block has a
strict decay contribution. The hierarchy is triangular from
\((\bar u,U)\) through \((\bar v,W,S)\) to
\((\bar r,Q,C,R)\), so it has a unique finite stationary solution on the
physical invariant manifold.

The orientation block is

\[
\begin{array}{c|cc}
q & \bar u & U\\ \hline
P,PV & 0 & I/2\\[2mm]
P\Theta,PV\Theta
& \dfrac{\rho}{1+\rho}e
& \operatorname{diag}\!\left(\dfrac{\rho+2}{\rho+4},
                              \dfrac{2}{\rho+4}\right).
\end{array}
\]

The velocity blocks are

\[
\begin{array}{c|cc}
q & \bar v & W\\ \hline
P
& \mathrm{Pe}\,\bar u
& \dfrac{\mathrm{Pe}\,U}{1+M}\\[2mm]
PV
& \dfrac{\mathrm{Pe}\,\bar u}{1+M\rho}
& \dfrac{\mathrm{Pe}\,U}{1+M(1+\rho)}\\[2mm]
P\Theta
& \mathrm{Pe}\,\bar u
& \dfrac{\mathrm{Pe}\,U+M\rho\,\bar v e^\mathsf T}
        {1+M(1+\rho)}\\[3mm]
PV\Theta
& \dfrac{\mathrm{Pe}\,\bar u}{1+M\rho}
& \dfrac{\mathrm{Pe}\,U}{1+M(1+\rho)}.
\end{array}
\]

For all four protocols,

\[
\begin{aligned}
\bar r&=\frac{\bar v}{\rho},\\
S&=\frac{\mathrm{Pe}(W+W^\mathsf T)+2I/M}
        {2+M\rho\,\mathbf 1_{\{V\ {\rm reset}\}}},\\
Q&=\frac{W}{1+\rho},\\
C&=\frac{MS+\mathrm{Pe}\,Q}{1+M\rho},\\
R&=\frac{C+C^\mathsf T}{\rho}.
\end{aligned}
\]

Consequently, all four position-reset protocols are stationary/localized
in centered position and have bounded raw MSD.

Traceability:
[accepted position-protocol solution](../artifacts/derived/T-020-position-protocols.md).

### S3.2 Long-time solution for non-position protocols

The internal \((v,u)\) blocks of \(V,\Theta,V\Theta\) are exactly the same as
those of \(PV,P\Theta,PV\Theta\), respectively. Define

\[
\Sigma_u=U-\bar u\bar u^\mathsf T,\qquad
\Sigma_v=S-\bar v\bar v^\mathsf T,\qquad
K=W-\bar v\bar u^\mathsf T.
\]

With

\[
\alpha=
\begin{cases}
1,&q=V,\\
1+\rho,&q=\Theta,V\Theta,
\end{cases}
\qquad
B=
\begin{cases}
1+M\rho,&q=V,V\Theta,\\
1,&q=\Theta,
\end{cases}
\]

the centered long-time transport law is

\[
\lim_{t\to\infty}\operatorname{Cov}(r,u)=\frac{K}{\alpha},
\qquad
\lim_{t\to\infty}\operatorname{Cov}(r,v)
=\frac{M\Sigma_v+\mathrm{Pe}\,K/\alpha}{B},
\]

\[
\operatorname{Cov}(r(t))=2Dt+O(1),\qquad
D=\frac{\operatorname{Cov}(r,v)+
        \operatorname{Cov}(r,v)^\mathsf T}{2},
\qquad
D_{\mathrm{eff}}=\frac{\operatorname{Tr}D}{2}.
\]

Thus all three non-position protocols are diffusive in centered covariance.
For \(V\), \(\bar v=0\), so raw MSD is also diffusive. For the two
orientation-reset protocols,

\[
\bar v_\Theta=\frac{\mathrm{Pe}\rho}{1+\rho}e,\qquad
\bar v_{V\Theta}
=\frac{\mathrm{Pe}\rho}{(1+\rho)(1+M\rho)}e.
\]

Their raw MSD is therefore ballistic exactly when
\(\mathrm{Pe}\rho>0\), even though their centered fluctuations are
diffusive.

Traceability:
[accepted non-position solution](../artifacts/derived/T-021-nonposition-protocols.md).

## S4. Exact 21-pair witness table

Assume in this section that

\[
M>0,\qquad \rho>0,\qquad \mathrm{Pe}\ge0,
\]

and that parameters and the common initial state are matched. The following
three rows are disjoint and give the exact partition
\(12 + 6 + 3 = 21=\binom72\) unordered pairs.

| Disjoint case | Exact pairs | Separating member of \(\mathcal R_2\) |
|---|---|---|
| Different position-reset indicator: \(12\) pairs | \(P/V,\ P/\Theta,\ P/V\Theta;\ PV/V,\ PV/\Theta,\ PV/V\Theta;\ P\Theta/V,\ P\Theta/\Theta,\ P\Theta/V\Theta;\ PV\Theta/V,\ PV\Theta/\Theta,\ PV\Theta/V\Theta\) | The position-reset member has finite stationary centered variance and bounded raw MSD; the non-position member has linearly growing centered covariance. This witness also holds at \(\mathrm{Pe}=0\). |
| Same position status, different orientation-reset indicator: \(6\) pairs | \(P/P\Theta,\ P/PV\Theta,\ PV/P\Theta,\ PV/PV\Theta,\ V/\Theta,\ V/V\Theta\) | At \(\rho>0\), the orientation-reset member has \(\bar u=\rho e/(1+\rho)\) and \(U=\operatorname{diag}((\rho+2)/(\rho+4),2/(\rho+4))\); the other member has \(\bar u=0\) and \(U=I/2\). This witness is independent of \(\mathrm{Pe}\). |
| Same position and orientation status, different velocity-reset indicator: \(3\) pairs | \(P/PV,\ P\Theta/PV\Theta,\ \Theta/V\Theta\) | For \(P/PV\), each \(S_{ii}\) has the strictly positive difference shown below. For the other two pairs, \(\bar v\) differs when \(\mathrm{Pe}>0\); at \(\mathrm{Pe}=0\), each diagonal velocity moment differs by \(\rho/(2+M\rho)>0\). |

For the \(P/PV\) pair, the all-activity witness is

\[
\begin{aligned}
S_{P,ii}-S_{PV,ii}
=
\frac{\rho\left[
M^2\mathrm{Pe}^2\rho+M^2\mathrm{Pe}^2+2M^2\rho+2M^2
+3M\mathrm{Pe}^2+2M\rho+4M+2\right]}
{2(M+1)(M\rho+2)(M\rho+M+1)}
>0 .
\end{aligned}
\]

Because every unordered pair occurs in exactly one row, these witnesses prove

\[
\boxed{
\mathcal R_2(X;M,\mathrm{Pe},\rho)
\ne
\mathcal R_2(Y;M,\mathrm{Pe},\rho)
\quad\text{for every }X\ne Y
}
\]

on the stated finite-parameter domain. The conclusion is full-record
distinguishability, not practical identifiability from finite noisy data.

Traceability:
[accepted exhaustive proposition](../artifacts/derived/T-030-memory-channel-proposition.md).

## S5. Restricted-identity ledger

The following exact equalities concern a named sector, contraction, condition,
resonance, or limit. None is equality of the full records. Except for the
full internal-process identities in S5.1, stationary or long-time quantities
are meant where a time argument is suppressed.

### S5.1 Internal-sector identities

For every finite physical parameter point,

\[
PV\equiv V,\qquad
P\Theta\equiv\Theta,\qquad
PV\Theta\equiv V\Theta
\quad\text{on the full internal }(v,u)\text{ process}.
\]

Position reset is absent from the \((v,u)\) generator. Hence all internal
means, \(S,W,U\), centered internal blocks, and higher internal statistics
match for each pair. Their spatial records do not match: the left member is
localized and the right member transports.

### S5.2 Contracted-observable degeneracies

For \(PV/PV\Theta\), the named scalar triple
\((\mathrm{TrS},\mathrm{TrC},\mathrm{TrR})\) agrees exactly:

\[
\boxed{
\operatorname{Tr}S_{PV}=\operatorname{Tr}S_{PV\Theta},\quad
\operatorname{Tr}C_{PV}=\operatorname{Tr}C_{PV\Theta},\quad
\operatorname{Tr}R_{PV}=\operatorname{Tr}R_{PV\Theta}.
}
\]

The equality follows from \(\operatorname{Tr}U=1\). It does not extend to
centered spatial variance; in the active positive-rate interior,

\[
\operatorname{Tr}\operatorname{Cov}_{PV}(r)
-\operatorname{Tr}\operatorname{Cov}_{PV\Theta}(r)
=\frac{\mathrm{Pe}^2}
{(1+\rho)^2(1+M\rho)^2}>0.
\]

For \(V/V\Theta\),

\[
\boxed{\operatorname{Tr}S_V=\operatorname{Tr}S_{V\Theta}}
\]

for all finite physical parameters. At \(\rho>0\), orientation moments
separate the records; in the active interior, \(V\Theta\) also drifts and
\(D_{\mathrm{eff},V}>D_{\mathrm{eff},V\Theta}\).

### S5.3 Resonant identity

For \(P/P\Theta\), each member of the named triple
\((\mathrm{TrS},\mathrm{TrC},\mathrm{TrR})\),

\[
\boxed{(\operatorname{Tr}S,\operatorname{Tr}C,\operatorname{Tr}R)}
\]

has a protocol difference proportional to
\(\mathrm{Pe}^2(M\rho-1)\). The triple therefore agrees at the passive
endpoint \(\mathrm{Pe}=0\) and on the active resonance

\[
\boxed{M\rho=1.}
\]

The full records remain distinct. For example, at
\(M=\rho=1\) and \(\mathrm{Pe}=6/5\),
\(\bar u_x\) is \(0\) for \(P\) and \(1/2\) for \(P\Theta\), while
\(\bar r_x\) is \(0\) and \(3/5\), respectively.

### S5.4 Conditional identities

At \(\mathrm{Pe}=0\), the translational sectors satisfy

\[
P=P\Theta,\qquad
PV=PV\Theta,\qquad
V=V\Theta,
\]

but orientation outputs still separate each pair for \(\rho>0\).

There is also an accepted analytic-only curve on which \(V\) and \(\Theta\)
have the same centered diffusion tensor:

\[
\boxed{
\rho=\frac12,\qquad
\mathrm{Pe}^2=
\frac{27M(M+6)(3M+2)}
{2(44-9M-80M^2-12M^3)},\qquad
0<M<M_\star
}
\]

where \(M_\star\) is the unique positive root of
\(44-9M-80M^2-12M^3=0\)
(\(M_\star=0.658170892\ldots\)). The denominator is positive on the
stated domain. This is not a full-record
identity: \(\Theta\) has nonzero mean drift and ballistic raw MSD, whereas
\(V\) has zero drift and diffusive raw MSD. The curve is an exact analytic
identity and was not part of the sampled numerical validation grid.

### S5.5 Limiting identities

At fixed \(\rho>0\) and \(\mathrm{Pe}\ge0\), first derive the exact
finite-\(M\) stationary position moments (for position-reset maps) or
long-time drift/diffusion coefficients (for non-position maps), and then take
the position-output limit \(M\to0^+\). In this order,

\[
P=PV,\qquad
P\Theta=PV\Theta,\qquad
\Theta=V\Theta
\quad\text{in their position-process outputs}.
\]

At \(\rho=0\), the jump term vanishes and all seven protocols reduce to the
same free process. The \(M\to0^+\) statement does not assert convergence of
the velocity record, a transient path-space topology, the reverse order, or
a joint reset-rate limit. Equal rare- or frequent-reset leading coefficients
are identities only of those named coefficients, not of the finite-rate
records.

Traceability:
[accepted classification and identity ledger](../artifacts/derived/V-020-equivalence-map.md)
and
[accepted proposition](../artifacts/derived/T-030-memory-channel-proposition.md).

## S6. Mandatory baselines and limits

### S6.1 Complete-reset baseline

For \(PV\Theta\), the stationary means reduce to

\[
\bar u=\frac{\rho}{1+\rho}e,\qquad
\bar v=\frac{\rho\,\mathrm{Pe}}
{(1+\rho)(1+M\rho)}e,\qquad
\bar r=\frac{\mathrm{Pe}}
{(1+\rho)(1+M\rho)}e.
\]

The complete component solution from S3.1 reproduces the accepted
complete-reset inertial baseline.

### S6.2 Zero-rate and rare-reset limit

For every position-reset protocol,

\[
\lim_{\rho\to0^+}\operatorname{Tr}S
=\frac{2}{M}+\frac{\mathrm{Pe}^2}{1+M},
\]

\[
\lim_{\rho\to0^+}\rho\,\operatorname{Tr}R
=4+2\mathrm{Pe}^2
=4D_{\mathrm{eff,free}},
\qquad
D_{\mathrm{eff,free}}=1+\frac{\mathrm{Pe}^2}{2}.
\]

For each non-position protocol,

\[
\lim_{\rho\to0^+}\bar v=0,\qquad
\lim_{\rho\to0^+}\operatorname{Tr}S
=\frac{2}{M}+\frac{\mathrm{Pe}^2}{1+M},
\]

\[
\lim_{\rho\to0^+}D
=\left(1+\frac{\mathrm{Pe}^2}{2}\right)I.
\]

The order matters for position resetting. At each fixed \(\rho>0\), first
taking \(t\to\infty\) produces a stationary position law; its variance then
diverges as \(\rho\to0^+\). Setting \(\rho=0\) first removes resetting and
produces free diffusion rather than a stationary law. The scaled limit above
connects these two descriptions without asserting that the two limits
commute.

### S6.3 Passive underdamped limit

At \(\mathrm{Pe}=0\), orientation reset drops out of translational moments.
For position-reset protocols,

\[
\begin{array}{c|cc}
\text{class} & S & R\\ \hline
P=P\Theta
& I/M
& \dfrac{2I}{\rho(1+M\rho)}\\[3mm]
PV=PV\Theta
& \dfrac{2I}{M(2+M\rho)}
& \dfrac{4I}{\rho(1+M\rho)(2+M\rho)}.
\end{array}
\]

For non-position protocols,

\[
D_\Theta=I,\qquad
D_V=D_{V\Theta}
=\frac{2I}{(1+M\rho)(2+M\rho)}.
\]

These are translational identities only; orientation records remain distinct
when \(\rho>0\).

### S6.4 Singular overdamped position-process limit

The \(M\to0^+\) comparison is a singular position-process limit. The limiting
equation is

\[
dr=\mathrm{Pe}\,u\,dt+\sqrt2\,dW_t.
\]

For the localized protocols, the accepted procedure is: solve the exact
finite-\(M\) stationary position moments at fixed
\((\rho,\mathrm{Pe})\), then take \(M\to0^+\). This gives

\[
P=PV,\qquad P\Theta=PV\Theta
\quad\text{in position second moments},
\]

\[
R_{\mathrm{od}}
=\frac{2I}{\rho}
+\frac{2\mathrm{Pe}^2U}{\rho(1+\rho)},
\]

\[
\bar r=
\begin{cases}
0,&P,PV,\\[1mm]
\mathrm{Pe}\,e/(1+\rho),&P\Theta,PV\Theta,
\end{cases}
\qquad
\operatorname{Cov}(r)=R_{\mathrm{od}}-\bar r\bar r^\mathsf T,
\]

where \(U=I/2\) without orientation reset and

\[
U=\operatorname{diag}\left(\frac{\rho+2}{\rho+4},
                           \frac{2}{\rho+4}\right)
\]

with orientation reset.

For the non-position protocols, compute the finite-\(M\) diffusion tensor
first and then take \(M\to0^+\):

\[
D_V\longrightarrow
\left(1+\frac{\mathrm{Pe}^2}{2}\right)I,
\qquad
D_\Theta\longrightarrow
I+\frac{\mathrm{Pe}^2}{1+\rho}\Sigma_u,
\qquad
D_{V\Theta}\longrightarrow
I+\frac{\mathrm{Pe}^2}{1+\rho}\Sigma_u.
\]

Velocity is not an independent state at \(M=0\). These statements therefore
assert convergence of the displayed position outputs, not convergence of
the finite-inertia velocity record. No direct substitution \(M=0\) is made
in a velocity formula. Any joint limit involving \(M\), \(\rho\), or
\(t\to\infty\) must state its order; the results above do not assert that
those limits commute.

### S6.5 Frequent-reset asymptotics

For position-reset protocols,

\[
\begin{aligned}
\lim_{\rho\to\infty}\rho^2E_P|r|^2
&=\frac4M+\frac{2\mathrm{Pe}^2}{1+M},\\
\lim_{\rho\to\infty}\rho^2E_{P\Theta}|r|^2
&=\frac4M+2\mathrm{Pe}^2,\\
\lim_{\rho\to\infty}\rho^3E_{PV}|r|^2
=\lim_{\rho\to\infty}\rho^3E_{PV\Theta}|r|^2
&=\frac8{M^2}.
\end{aligned}
\]

For \(P\Theta\),
\(\lim_{\rho\to\infty}\rho^2|\bar r|^2=\mathrm{Pe}^2\), so its centered
variance coefficient is \(4/M+\mathrm{Pe}^2\).

For non-position protocols,

\[
\begin{aligned}
\lim_{\rho\to\infty}\rho^2D_{\mathrm{eff},V}
&=\frac{\mathrm{Pe}^2+4}{2M^2},\\
\lim_{\rho\to\infty}D_{\mathrm{eff},\Theta}
&=1,\qquad
\lim_{\rho\to\infty}\bar v_\Theta=\mathrm{Pe}\,e,\\
\lim_{\rho\to\infty}\rho^2D_{\mathrm{eff},V\Theta}
&=\frac2{M^2},\qquad
\lim_{\rho\to\infty}\rho\bar v_{V\Theta}
=\frac{\mathrm{Pe}}{M}e.
\end{aligned}
\]

For every fixed finite \(\rho>0\), \(\Theta\) and \(V\Theta\) have a
ballistic raw-MSD term whenever \(\mathrm{Pe}>0\). The vanishing
\(V\Theta\) drift coefficient as \(\rho\to\infty\) does not retroactively
change that finite-rate classification. This is another noncommuting
classification/asymptotic distinction: a leading coefficient may vanish in
a parameter limit although the finite-parameter growth exponent remains
ballistic.

## S7. Claim boundary

The exact result is full-record second-order distinguishability of all seven
nonempty reset maps for \(M>0\), \(\rho>0\), and
\(\mathrm{Pe}\ge0\), together with a scope-labeled ledger of information
loss under internal-sector restriction, scalar contraction, special
parameter conditions, resonance, and singular limits. Trace equality is not
matrix equality; raw-MSD equality is not centered-covariance equality; and
none of the restricted identities is full protocol equivalence.

The supplement makes no practical-identifiability claim and introduces no
higher-order or distributional claim.

## S8. Source crosswalk

- Model, reset maps, required observables, identity labels, and mandatory
  limits:
  [scientific contract](../docs/scientific-contract/CONTRACT.md).
- Exact generator, ordered redundant frame, and fail-closed closure construction:
  [generator.py](../src/phasemap/theory/generator.py).
- Position-reset stationary solution and limits:
  [T-020](../artifacts/derived/T-020-position-protocols.md).
- Non-position centered transport law and limits:
  [T-021](../artifacts/derived/T-021-nonposition-protocols.md).
- Full-record proposition and exhaustive separating proof:
  [T-030](../artifacts/derived/T-030-memory-channel-proposition.md).
- Exact classification, restricted identities, resonance, and tuned
  diffusion curve:
  [V-020](../artifacts/derived/V-020-equivalence-map.md).
