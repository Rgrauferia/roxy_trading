"""Explicit choices can reference actual records without becoming recorded results."""
from copy import deepcopy

import pytest
from pydantic import TypeAdapter, ValidationError

from roxy_os.fitness import training_content
from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.repository import FitnessConflict, FitnessStorageUnavailable
from roxy_os.fitness.training_targets import (
    TrainingTargets, TrainingTargetExercise, targets_from_log, validate_training_targets,
)

PROGRAM = 'home-dumbbell-foundations'
VERSION = training_content.training_detail(PROGRAM)['content_version']
DETAIL = {'content_version': 'test-v1', 'exercises': [
    {'id': 'prepare', 'phase': 'warmup', 'tracking_unit': 'seconds', 'load_recordable': False},
    {'id': 'move-reps', 'phase': 'work', 'tracking_unit': 'reps', 'load_recordable': True},
    {'id': 'hold-seconds', 'phase': 'work', 'tracking_unit': 'seconds', 'load_recordable': False},
    {'id': 'finish', 'phase': 'cooldown', 'tracking_unit': 'seconds', 'load_recordable': False},
]}


@pytest.fixture
def content(monkeypatch):
    monkeypatch.setattr(training_content, 'training_detail', lambda _id: deepcopy(DETAIL))


def target(exercise_id='move-reps', **series):
    return {'exercise_id': exercise_id, 'sets': [series or {'reps': 8}]}


def record():
    return {'program_id': 'test-program', 'content_version': 'test-v1', 'exercises': [
        {'exercise_id': 'move-reps', 'skipped': False, 'sets': [
            {'reps': 8, 'seconds': None, 'load': {'value': 10, 'unit': 'lb'}, 'load_kg': 4.535924},
            {'reps': 6, 'seconds': None, 'load': None, 'load_kg': None},
        ]},
        {'exercise_id': 'hold-seconds', 'skipped': True, 'sets': []},
    ]}


def test_absence_remains_absent_without_reading_content(monkeypatch):
    monkeypatch.setattr(training_content, 'training_detail', lambda _: pytest.fail('Unexpected content read'))
    assert validate_training_targets('historical-program', 'old-v1', None) is None


def test_partial_targets_are_canonical_in_content_order_and_not_original_doses(content):
    chosen = [target('hold-seconds', seconds=1.5), target(reps=3, load={'value': 0, 'unit': 'kg'})]
    result = validate_training_targets('test-program', 'test-v1', chosen)
    assert result == [
        {'exercise_id': 'move-reps', 'sets': [{'reps': 3, 'seconds': None, 'load': {'value': 0.0, 'unit': 'kg'}}]},
        {'exercise_id': 'hold-seconds', 'sets': [{'reps': None, 'seconds': 1.5, 'load': None}]},
    ]
    assert len(validate_training_targets('test-program', 'test-v1', [target()])) == 1
    assert 'seconds' not in chosen[1]['sets'][0]


def test_schema_objects_are_accepted_for_api_and_plan_boundaries(content):
    parsed = [TrainingTargetExercise.model_validate(target())]
    assert validate_training_targets('test-program', 'test-v1', parsed)[0]['sets'][0]['reps'] == 8


@pytest.mark.parametrize('entry', [
    [], [target(), target()], [target('prepare', seconds=30)], [target('finish', seconds=30)],
    [target('not-a-movement')], [target(seconds=30)], [target('hold-seconds', reps=8)],
    [target('hold-seconds', seconds=30, load={'value': 5, 'unit': 'kg'})],
    [{'exercise_id': 'move-reps', 'sets': []}],
    [{'exercise_id': 'move-reps', 'sets': [{'reps': 8}] * 21}],
    [dict(target(), skipped=False)], [target(reps=8, load_kg=3)],
])
def test_invalid_exercises_units_and_structures_rejected(content, entry):
    with pytest.raises((ValidationError, FitnessInputError)):
        validate_training_targets('test-program', 'test-v1', entry)


@pytest.mark.parametrize('value', [True, False, '8', 1.5, 0, -1, 10001, float('inf'), float('nan')])
def test_repetitions_are_strict_positive_integers(content, value):
    with pytest.raises(ValidationError):
        validate_training_targets('test-program', 'test-v1', [target(reps=value)])


@pytest.mark.parametrize('value', [True, '8', 0, -1, 86401, float('inf'), float('-inf'), float('nan'), 10**1000])
def test_seconds_are_strict_finite_numbers(content, value):
    with pytest.raises(ValidationError):
        validate_training_targets('test-program', 'test-v1', [target('hold-seconds', seconds=value)])


@pytest.mark.parametrize('value', [True, '8', -1, 2501, float('inf'), float('nan'), 10**1000])
def test_load_is_optional_and_strictly_finite(content, value):
    with pytest.raises(ValidationError):
        validate_training_targets('test-program', 'test-v1', [target(reps=8, load={'value': value, 'unit': 'kg'})])


@pytest.mark.parametrize('series', [{}, {'reps': None}, {'reps': 8, 'seconds': 30}, {'reps': 8, 'load': {'value': 5, 'unit': 'stone'}}])
def test_each_target_set_has_one_axis_and_declared_load_units(content, series):
    with pytest.raises(ValidationError):
        TypeAdapter(TrainingTargets).validate_python([{'exercise_id': 'move-reps', 'sets': [series]}])


def test_schema_bounds_do_not_change_content_or_derive_loads(content):
    result = validate_training_targets('test-program', 'test-v1', [
        target(reps=10000, load={'value': 2500, 'unit': 'lb'}), target('hold-seconds', seconds=86400),
    ])
    assert result[0]['sets'][0]['load'] == {'value': 2500.0, 'unit': 'lb'}
    assert result[1]['sets'][0]['seconds'] == 86400


def test_changed_content_cannot_be_used_for_new_targets(content):
    with pytest.raises(FitnessConflict):
        validate_training_targets('test-program', 'older-v0', [target()])


def test_unknown_content_is_an_input_error(monkeypatch):
    def missing(_id):
        raise training_content.TrainingContentError('missing')
    monkeypatch.setattr(training_content, 'training_detail', missing)
    with pytest.raises(FitnessInputError):
        validate_training_targets('missing', 'test-v1', [target()])


def test_invalid_editorial_contract_is_unavailable(monkeypatch):
    broken = deepcopy(DETAIL)
    broken['exercises'].append(broken['exercises'][1])
    monkeypatch.setattr(training_content, 'training_detail', lambda _id: broken)
    with pytest.raises(FitnessStorageUnavailable):
        validate_training_targets('test-program', 'test-v1', [target()])


def test_record_projection_keeps_original_units_counts_and_source_unmodified(content):
    saved = record()
    original = deepcopy(saved)
    result = targets_from_log(saved)
    assert result == [{'exercise_id': 'move-reps', 'sets': [
        {'reps': 8, 'seconds': None, 'load': {'value': 10.0, 'unit': 'lb'}},
        {'reps': 6, 'seconds': None, 'load': None},
    ]}]
    assert saved == original
    assert not any('load_kg' in series for entry in result for series in entry['sets'])
    assert all(entry['exercise_id'] != 'hold-seconds' for entry in result)


def test_all_omitted_remains_without_targets_and_does_not_fill_doses(content):
    saved = record()
    saved['exercises'][0].update(skipped=True, sets=[])
    assert targets_from_log(saved) is None


@pytest.mark.parametrize('alter', [
    lambda r: r.update(exercises=[]),
    lambda r: r['exercises'].append(r['exercises'][0]),
    lambda r: r['exercises'][1].update(exercise_id='move-reps'),
    lambda r: r['exercises'][0].update(skipped=True),
    lambda r: r['exercises'][0].update(skipped='false'),
    lambda r: r['exercises'][0].update(sets=[]),
    lambda r: r['exercises'][0]['sets'][0].update(calories=123),
    lambda r: r['exercises'][0]['sets'][0].update(seconds=10),
])
def test_projection_rejects_corrupted_saved_records(content, alter):
    saved = record(); alter(saved)
    with pytest.raises((ValidationError, FitnessInputError)):
        targets_from_log(saved)


def test_all_six_actual_routines_accept_partial_choices_with_their_real_units():
    for summary in training_content.training_catalog()['programs']:
        detail = training_content.training_detail(summary['id'])
        movement = next(ex for ex in detail['exercises'] if ex['phase'] == 'work')
        chosen = [target(movement['id'], **{movement['tracking_unit']: 4})]
        result = validate_training_targets(detail['id'], detail['content_version'], chosen)
        assert len(result) == 1
        assert result[0]['sets'][0][movement['tracking_unit']] == 4
        assert result[0]['sets'][0]['load'] is None
