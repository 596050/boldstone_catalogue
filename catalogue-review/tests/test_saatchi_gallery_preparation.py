import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('gallery_preparation',
    Path(__file__).parents[1] / 'scripts' / 'prepare_saatchi_galleries.py')
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)


def photos(roles):
    return [{'id': str(i), 'role': role} for i, role in enumerate(roles)]


def test_native_cap_preserves_product_and_setting_views_in_source_order():
    source = photos(['listing'] * 6 + ['in_situ'] * 4)
    selected, overflow = gallery.select_additions(source)
    assert [p['id'] for p in selected] == ['0', '1', '2', '6', '7']
    assert len(selected) == 5
    assert len(overflow) == 5
    assert {p['id'] for p in selected + overflow} == {p['id'] for p in source}


@pytest.mark.parametrize('roles', [[], ['listing'], ['in_situ'] * 5, ['listing'] * 4 + ['in_situ']])
def test_galleries_that_fit_are_preserved(roles):
    source = photos(roles)
    selected, overflow = gallery.select_additions(source)
    assert selected == source
    assert overflow == []


@pytest.mark.parametrize('roles', [['listing'] * 9, ['in_situ'] * 9,
    ['listing'] * 2 + ['in_situ'] * 6, ['listing'] * 8 + ['in_situ']])
def test_unused_slots_are_filled_without_losing_overflow(roles):
    source = photos(roles)
    selected, overflow = gallery.select_additions(source)
    assert len(selected) == 5
    assert len(overflow) == len(source) - 5
    assert len({p['id'] for p in selected + overflow}) == len(source)


def test_duplicate_source_photographs_are_rejected():
    with pytest.raises(ValueError, match='Duplicate photograph'):
        gallery.select_additions([{'id': 'same', 'role': 'listing'}] * 2)


def test_smaller_native_limit_still_respected():
    selected, overflow = gallery.select_additions(photos(['listing', 'in_situ', 'in_situ']), 1)
    assert len(selected) == 1
    assert len(overflow) == 2


def test_invalid_limit_rejected():
    with pytest.raises(ValueError, match='At least one'):
        gallery.select_additions([], 0)
