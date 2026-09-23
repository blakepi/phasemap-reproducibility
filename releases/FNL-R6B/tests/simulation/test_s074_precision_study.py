"""Prospective design checks: no scientific trajectory production."""

from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
import sympy as sp
import experiments.run_s074_precision as runner

from experiments.run_s074_precision import (
    allocate_cell, classify_row, freeze_case, freeze_plan, load_plan, make_cases,
    merge_accumulator_states, propagate_reference_moments, record_times,
    reference_rows, save_npz_immutable, source_manifest, step_for_case,
    validate_plan,
)
from phasemap.simulation.protocols import Protocol
from phasemap.theory.nonposition_protocols import nonposition_protocol_second_moments


V2_PLAN_PATH = Path(__file__).resolve().parents[2] / 'experiments/S-074-precision-primary-v2.json'


def test_declared_cells_and_observables_are_complete():
    plan = load_plan()
    validate_plan(plan)
    cases = make_cases(plan)
    assert len(cases) == 41
    assert len({c['id'] for c in cases}) == 41
    assert {c['protocol'] for c in cases if c['group'] == 'core'} == {p.value for p in Protocol}
    assert sum(len(reference_rows(c)) for c in cases) == 80
    assert all(0 < step_for_case(c, plan) <= min(1/512, c['M']/200, 1/(200*c['rho'])) for c in cases)


@pytest.mark.parametrize('field,value', [('pilot_reuse', True), ('result_dependent_stopping', True), ('production_seed', 740620260901), ('evidence_tier', 'routine_screen'), ('target_relative_se', 0.02)])
def test_plan_fails_closed_for_scientific_drift(field, value):
    plan = deepcopy(load_plan())
    plan[field] = value
    with pytest.raises(ValueError):
        validate_plan(plan)


def test_reference_scales_and_zero_dispatch():
    cases = make_cases(load_plan())
    rows = {r['observable']: r for r in reference_rows(next(c for c in cases if c['id'] == 'core-V'))}
    zero = rows['v_x']
    assert zero['reference'] == 0
    assert zero['observable_class'] == 'symmetry_forced_zero'
    assert zero['epsilon'] == pytest.approx(0.005 * zero['characteristic_scale'])
    spatial = rows['spatial']
    assert spatial['observable_class'] == 'd_eff'
    assert spatial['characteristic_scale'] == max(abs(spatial['reference']), 1)


def test_expanded_interval_and_precision_are_separate():
    row = {'reference': 2., 'precision_scale': 2., 'epsilon': .03}
    ok = classify_row(row, value=2., se=.001, b_disc=.001, b_window=.001)
    assert ok['classification'] == 'validated' and ok['precision_pass']
    contrary = classify_row(row, value=3., se=.001, b_disc=0., b_window=0.)
    assert contrary['classification'] == 'contradicted' and contrary['precision_pass']
    assert classify_row(row, value=2., se=.02, b_disc=0., b_window=0.)['classification'] == 'unresolved'
    with pytest.raises(ValueError):
        classify_row(row, value=np.nan, se=.001, b_disc=0., b_window=0.)


def test_records_and_source_identity():
    times = record_times(160, load_plan())
    assert len(times) == 65 and times[0] == 0 and times[-1] == 160
    assert np.all(np.diff(times) > 0)
    manifest = source_manifest()
    assert 'src/phasemap/simulation/gpu_trajectories.py' in manifest
    assert all(len(value) == 64 for value in manifest.values())


def test_velocity_retaining_competition_matches_independent_moments():
    M, Pe, rho = sp.symbols('M Pe rho', positive=True)
    result = nonposition_protocol_second_moments(Protocol.THETA, M, Pe, rho)
    decomposition = 2/M + Pe**2*(1+2*rho)/(1+rho)**2/(1+M*(1+rho)) + (Pe*rho/(1+rho))**2
    free = 2/M + Pe**2/(1+M)
    difference = Pe**2*M*rho*(M*rho-1)/((1+M)*(1+rho)*(1+M*(1+rho)))
    assert sp.factor(result.stationary_mean_squared_speed - decomposition) == 0
    assert sp.factor(decomposition-free-difference) == 0


def test_generator_propagation_starts_from_declared_zero_state():
    case = next(c for c in make_cases(load_plan()) if c['id'] == 'core-PVTheta')
    propagated, names = propagate_reference_moments(case, np.array([0.0, 0.125]))
    initial = dict(zip(names, propagated[0]))
    assert initial['one'] == 1
    assert initial['u_x'] == 1 and initial['uu_xx'] == 1
    assert all(
        initial[name] == 0
        for name in names
        if name not in {'one', 'u_x', 'uu_xx'}
    )
    assert np.all(np.isfinite(propagated))


def test_frozen_horizon_meets_every_declared_transient_budget():
    plan = load_plan()
    case = next(c for c in make_cases(plan) if c['id'] == 'core-PVTheta')
    frozen = freeze_case(case, plan)
    assert frozen['horizon'] >= 64
    assert frozen['horizon'] <= plan['maximum_horizon']
    assert frozen['record_times'][0] == 0
    assert frozen['record_times'][-1] == frozen['horizon']
    assert all(
        row['transient_residual']
        <= row['epsilon'] / plan['transient_margin_divisor']
        for row in frozen['rows']
    )


def test_expanded_freeze_material_is_exactly_41_cells_80_rows():
    plan = load_plan()
    cells = [freeze_case(case, plan) for case in make_cases(plan)]
    assert len(cells) == 41
    assert sum(len(cell['rows']) for cell in cells) == 80
    assert all(len(cell['record_times']) == 65 for cell in cells)
    assert all(len(cell['layout_sha256']) == 64 for cell in cells)
    assert all(
        len(row['transient_residuals']) == 3
        and row['transient_residual'] == max(row['transient_residuals'])
        for cell in cells for row in cell['rows']
    )


def test_expanded_freeze_transaction_is_immutable_and_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, '_environment_manifest', lambda: {
        'python': '3.12.0', 'python_implementation': 'CPython', 'platform': 'test',
        'numpy': '2.5.1', 'cupy': '14.2.0', 'cuda_runtime': 12090,
        'cuda_driver': 13030, 'gpu_device_id': 0, 'gpu_name': 'test GPU',
        'gpu_total_memory': 8_000_000_000,
    })
    first = freeze_plan(output_dir=tmp_path)
    second = freeze_plan(output_dir=tmp_path)
    assert first['freeze_file_sha256'] == second['freeze_file_sha256']
    assert first['execution_backend'] == 'gpu'
    assert len(first['cases']) == 41
    assert sum(len(cell['rows']) for cell in first['cases']) == 80
    assert all(cell['layout_sha256'] for cell in first['cases'])
    assert 'python_executable' not in first['environment']


def test_gpu_freeze_rejects_missing_device_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner, '_environment_manifest',
        lambda: {'python': '3.12.0', 'numpy': '2.5.1', 'cuda_probe_error': 'missing'},
    )
    with pytest.raises(RuntimeError, match='live GPU identity'):
        freeze_plan(output_dir=tmp_path)


def test_allocation_uses_stricter_se_target_and_never_clips_cap():
    plan = load_plan()
    rows = [{'id': 'a', 'precision_scale': 2.0, 'epsilon': 0.03}]
    q = 2.5758293035
    tau = min(0.02, 0.03 / (3 * q))
    diagnostics = {
        'rows': [{'id': 'a', 'fine': {'se': tau}}],
        'qualification_pass': True,
    }
    outcome = allocate_cell(plan, rows, diagnostics)
    assert outcome['n'] == 32768
    impossible = deepcopy(diagnostics)
    impossible['rows'][0]['fine']['se'] = 100.0
    assert allocate_cell(plan, rows, impossible)['feasible'] is False
    unqualified = deepcopy(diagnostics)
    unqualified['qualification_pass'] = False
    assert allocate_cell(plan, rows, unqualified)['feasible'] is False
    duplicated = deepcopy(diagnostics)
    duplicated['rows'].append(deepcopy(duplicated['rows'][0]))
    with pytest.raises(ValueError, match='identities'):
        allocate_cell(plan, rows, duplicated)


def test_accumulator_merge_and_immutable_npz_resumption(tmp_path):
    left = {'n': 2, 'mean': np.array([1.0]), 'm2': np.array([[2.0]])}
    right = {'n': 3, 'mean': np.array([4.0]), 'm2': np.array([[6.0]])}
    merged = merge_accumulator_states([left, right])
    assert merged['n'] == 5
    assert merged['mean'][0] == pytest.approx(2.8)
    assert merged['m2'][0, 0] == pytest.approx(18.8)

    target = tmp_path / 'batch.npz'
    arrays = {'n': np.array(5), 'mean': merged['mean'], 'm2': merged['m2']}
    first = save_npz_immutable(target, arrays)
    second = save_npz_immutable(target, arrays)
    assert first == second and len(first) == 64
    with pytest.raises(RuntimeError, match='immutable'):
        save_npz_immutable(target, arrays | {'mean': np.array([9.0])})


def test_receipt_metadata_and_unexpected_artifacts_fail_closed(tmp_path):
    case = {'id': 'cell', 'layout_sha256': 'a' * 64}
    expected = runner._receipt_expected(
        phase='production', case=case, seed=7, offset=0, n=8,
        freeze_hash='b' * 64, source_hash='c' * 64,
        environment_hash='d' * 64, backend='gpu',
    )
    artifact = tmp_path / 'batch-000000.npz'
    artifact_hash = save_npz_immutable(artifact, {'x': np.array([1.0])})
    receipt = tmp_path / 'batch-000000.json'
    runner._save_json_immutable(
        receipt, {**expected, 'seed': 8, 'artifacts': {'accumulator': artifact_hash}}
    )
    with pytest.raises(RuntimeError, match='metadata mismatch'):
        runner._verify_receipt(receipt, expected, {'accumulator': artifact})

    production = tmp_path / 'production' / 'cell'
    production.mkdir(parents=True)
    (production / 'unexpected.txt').write_text('tamper', encoding='utf-8')
    with pytest.raises(RuntimeError, match='unexpected production artifact'):
        runner._production_indices(tmp_path, 'cell')


def test_pilot_diagnostics_are_strict_json_round_trip(tmp_path):
    plan = load_plan()
    case = freeze_case(
        next(case for case in make_cases(plan) if case['id'] == 'core-P'), plan
    )
    rng = np.random.default_rng(7406)
    paths = rng.normal(size=(3, 65, 8, 5))
    features, layout = runner.build_features(paths, case['record_times'], case['mode'])
    assert layout == case['layout']
    accumulator = runner.FeatureAccumulator().add(features)
    diagnostics = runner._diagnostics(
        case,
        {'n': accumulator.n, 'mean': accumulator.mean, 'm2': accumulator.m2},
        features,
        {**plan, 'bootstrap_replicates': 8},
        bootstrap=True,
    )

    target = tmp_path / 'diagnostics.json'
    runner._save_json_immutable(target, diagnostics)
    loaded = json.loads(target.read_text(encoding='utf-8'))
    assert loaded == json.loads(json.dumps(diagnostics, allow_nan=False))
    assert isinstance(loaded['qualification_pass'], bool)
    assert all(
        isinstance(row['step_qualification_pass'], bool)
        and isinstance(row['qualification_pass'], bool)
        and isinstance(row['b1']['pass'], bool)
        and isinstance(row['b2']['pass'], bool)
        and (
            'bootstrap' not in row or isinstance(row['bootstrap']['pass'], bool)
        )
        for row in loaded['rows']
    )


def test_v2_plan_is_only_the_authorized_resource_revision():
    old = load_plan()
    new = load_plan(V2_PLAN_PATH)
    validate_plan(new)
    allowed = {
        'plan_id', 'version', 'output_directory', 'maximum_cell_n',
        'maximum_total_n', 'pilot_origin_directory',
        'pilot_origin_freeze_sha256', 'resource_amendment',
    }
    assert {key: value for key, value in old.items() if key not in allowed} == {
        key: value for key, value in new.items() if key not in allowed
    }
    assert new['maximum_cell_n'] == 2_097_152
    assert new['maximum_total_n'] == 33_554_432
    assert new['pilot_origin_directory'] == 'artifacts/raw/S-074-precision-primary-v1-iofix'
    assert new['pilot_origin_freeze_sha256'] == (
        '118e435e4752789dc7a98121cda4c1047593b28374a9541839dcce23add5ce63'
    )
    assert new['resource_amendment'] == (
        'docs/scientific-contract/S-074_RESOURCE_CAP_EXTENSION.md'
    )
    manifest = source_manifest()
    assert new['resource_amendment'] in manifest
    assert manifest[new['resource_amendment']] == (
        '7634d26dbc1d250eede46d4105917d4196db95b922ef3db5be84be66be1da3ac'
    )


def test_v2_plan_still_fails_closed_on_scientific_drift():
    changed = deepcopy(load_plan(V2_PLAN_PATH))
    changed['target_relative_se'] = 0.02
    with pytest.raises(ValueError, match='reviewed semantic identity'):
        validate_plan(changed)


def test_v2_pilot_command_verifies_origin_without_calling_producer(monkeypatch):
    plan = load_plan(V2_PLAN_PATH)
    cases = [freeze_case(case, plan) for case in make_cases(plan)]
    freeze = {
        'plan': plan,
        'cases': cases,
        'source_manifest_sha256': 's' * 64,
        'environment_sha256': 'e' * 64,
    }
    monkeypatch.setattr(runner, '_load_freeze', lambda *_: (freeze, Path('unused'), 'f' * 64))
    monkeypatch.setattr(
        runner, '_pilot_evidence_context',
        lambda *_: (freeze, Path('origin'), 'o' * 64),
    )
    monkeypatch.setattr(
        runner, '_verified_origin_pilot_diagnostics',
        lambda *_: {
            'case_id': _[0]['id'], 'n': 4096,
            'rows': [{'id': row['id']} for row in _[0]['rows']],
            'qualification_pass': True,
        },
        raising=False,
    )
    monkeypatch.setattr(
        runner, '_simulate_features',
        lambda *_args, **_kwargs: pytest.fail('v2 pilot called the producer'),
    )

    diagnostics = runner.run_pilot(V2_PLAN_PATH)
    assert len(diagnostics) == 41
    assert sum(len(item['rows']) for item in diagnostics) == 80


def _synthetic_pilot_origin(tmp_path, monkeypatch):
    old_plan = load_plan()
    new_plan = deepcopy(load_plan(V2_PLAN_PATH))
    cases = [freeze_case(case, old_plan) for case in make_cases(old_plan)]
    environment = {'gpu_name': 'fixed test GPU', 'cupy': '14.2.0'}
    sources = {path: 'a' * 64 for path in runner.COMMON_NUMERICAL_SOURCES}
    origin = {
        'plan': old_plan,
        'plan_semantic_sha256': runner.EXPECTED_PLAN_SEMANTIC_SHA256[old_plan['plan_id']],
        'environment': environment,
        'environment_sha256': runner._sha256_bytes(runner._semantic_bytes(environment)),
        'source_manifest': sources,
        'source_manifest_sha256': runner.source_manifest_digest(sources),
        'cases': cases,
    }
    origin['freeze_identity_sha256'] = runner._freeze_identity(origin)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    origin_path = tmp_path / new_plan['pilot_origin_directory'] / 'freeze.json'
    runner._save_json_immutable(origin_path, origin)
    new_plan['pilot_origin_freeze_sha256'] = runner._file_sha256(origin_path)
    active = {
        'plan': new_plan,
        'environment': environment,
        'environment_sha256': origin['environment_sha256'],
        'source_manifest': dict(sources),
        'source_manifest_sha256': origin['source_manifest_sha256'],
        'cases': deepcopy(cases),
    }
    return active


def test_v2_origin_hash_corruption_fails_closed(tmp_path, monkeypatch):
    active = _synthetic_pilot_origin(tmp_path, monkeypatch)
    active['plan']['pilot_origin_freeze_sha256'] = '0' * 64
    with pytest.raises(RuntimeError, match='origin freeze hash mismatch'):
        runner._pilot_evidence_context(active, tmp_path / 'active', 'b' * 64)


def test_v2_origin_rejects_scientific_field_drift(tmp_path, monkeypatch):
    active = _synthetic_pilot_origin(tmp_path, monkeypatch)
    active['plan']['target_relative_se'] = 0.02
    with pytest.raises(RuntimeError, match='scientific field'):
        runner._pilot_evidence_context(active, tmp_path / 'active', 'b' * 64)


def test_v2_origin_requires_exact_cases_layouts_and_rows(tmp_path, monkeypatch):
    active = _synthetic_pilot_origin(tmp_path, monkeypatch)
    active['cases'][0]['rows'] = active['cases'][0]['rows'][:-1]
    with pytest.raises(RuntimeError, match='cells, layouts, rows, steps, or horizons'):
        runner._pilot_evidence_context(active, tmp_path / 'active', 'b' * 64)


def test_v2_pinned_pilot_projects_authorized_fixed_counts():
    origin_path = (
        Path(__file__).resolve().parents[2]
        / 'artifacts/raw/S-074-precision-primary-v1-iofix/freeze.json'
    )
    if not origin_path.is_file():
        pytest.skip('pinned local pilot evidence is not present')
    origin = json.loads(origin_path.read_text(encoding='utf-8'))
    plan = load_plan(V2_PLAN_PATH)
    sources = source_manifest()
    active = {
        **origin,
        'plan': plan,
        'plan_semantic_sha256': runner.EXPECTED_PLAN_SEMANTIC_SHA256[plan['plan_id']],
        'source_manifest': sources,
        'source_manifest_sha256': runner.source_manifest_digest(sources),
    }
    diagnostics = runner._verified_pilot_set(
        active, Path(plan['output_directory']), 'active-freeze-placeholder'
    )
    projected = [
        allocate_cell(plan, case['rows'], diagnostics[case['id']])
        for case in active['cases']
    ]
    assert all(item['feasible'] for item in projected)
    assert sum(item['required_n'] for item in projected) == 23_519_232
    assert max(item['required_n'] for item in projected) == 1_146_880
