# T-010 generator and second-moment scaffold

## Result

The contract-v0.3 backward generator was audited and extended with a common,
full-state representation of all seven deterministic reset maps and an exact
linear second-order moment system. No contract change was required.

## Closed state

The generator closes on 28 raw observables:

- constant `1`;
- six means: the two components of `r`, `v`, and `u`;
- three independent components each of symmetric `rr`, `vv`, and `uu`;
- four components each of nonsymmetric `rv`, `ru`, and `vu`.

This is the complete component-level set required by contract section 4. The
derived scalars `E[|r|^2]`, `E[|v|^2]`, and `E[r dot v]` are exact linear
combinations of the raw state. Centered covariance quantities are derived from
these raw moments and the means; they do not enlarge the generator closure.
The 28-entry representation deliberately retains both orientation diagonal
moments and is therefore subject to the exact identity
`E[u_x^2] + E[u_y^2] = 1`. The matrix builder uses uncollapsed differential
and jump terms to select one consistent coordinate representation of this
redundant raw state across protocols and limits.

`second_order_moment_system` constructs the exact matrix `A` in
`d E[m]/dt = A E[m]`. It fails closed with `MomentClosureError` if any generator
image contains a monomial outside the declared state. The constant is retained
because orientation reset makes some jump terms affine, for example
`cos(theta) -> 1`.

## Reset representation

`reset_map` returns the complete image `(x, y, vx, vy, theta)` for a protocol.
`reset_substitution` and the jump generator both use that representation. Tests
enumerate all seven contract maps, including unchanged components.

## Exact checks and limits

- The 28 generator images reconstruct exactly from the declared state for each
  of seven protocols: 196 symbolic closure checks.
- Setting `rho=0` in every reset matrix exactly recovers the free generator.
- Setting `Pe=0` recovers the passive underdamped first- and second-velocity
  generators, including the `2/M^2` diffusion term.
- The contract declares `M -> 0` a singular position-process limit in which
  velocity ceases to be an independent state. This scaffold therefore does not
  perform invalid direct substitution of `M=0` into the finite-inertia matrix.

## Scope and limitations

This task identifies and verifies closure; it does not solve the moment ODEs,
classify long-time behavior, select the G4 discriminator, or make equivalence
claims. Those require downstream tasks and the contract's applicable gates.
