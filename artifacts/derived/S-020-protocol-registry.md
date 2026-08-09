# S-020: Shared all-seven reset registry

## Result

Implemented one canonical `PROTOCOL_REGISTRY` for the seven contract-v0.3
Dirac reset maps: `P`, `V`, `Theta`, `PV`, `PTheta`, `VTheta`, and `PVTheta`.
Each entry declares only whether position, velocity, and orientation are reset
to their fixed zero references. `apply_reset(state, protocol)` remains the
single reset-map API, and `simulate(params, protocol, config, initial_state)`
remains the single exact-clock engine for every protocol.

The exported registry is read-only and `apply_reset` rejects non-`Protocol`
inputs, preventing runtime mutation or string-key aliasing from changing the
contract-defined map.

## Contract and tests

The implementation matches CONTRACT sections 2--3: unlisted state components
are preserved, the map is non-mutating, and a reset records the integrated
pre-reset state then its mapped post-reset state at the same timestamp without
advancing time. Simulation tests cover every observed reset event for all seven
protocols at absolute tolerance `1e-12`; registry tests lock the exact member
set and component flags, immutability, and invalid-input rejection.

## Scope

No protocol-specific simulator was added. This is deterministic API and event
semantics evidence only; it makes no second-order classification claim.
