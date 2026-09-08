from copy import deepcopy
from pathlib import Path

import pytest

from roxy_os.home_food import HomeFoodStore
from roxy_os.home_recipe_fallback import exact_local_recipe, generate_local_recipe, local_recipe_catalog


@pytest.mark.parametrize('title,category', [
    ('Huevos con tostada integral', 'breakfast'), ('Panqueques de avena', 'breakfast'),
    ('Tortilla francesa con queso', 'breakfast'), ('Tostada de aguacate y huevo', 'breakfast'),
    ('Pizza casera', 'baked'),
])
def test_originals_keep_their_actual_category(title, category):
    recipe = exact_local_recipe(title)
    assert recipe['category'] == category
    assert 'Corta o desmenuza la proteína' not in ' '.join(recipe['steps'])


def test_saved_catalog_egg_correction_preserves_user_metadata_and_imports():
    saved = {'title':'Huevos con tostada integral', 'id':'kept', 'servings':1,
             'ingredients':[], 'steps':['Cocina la proteína a 63 °C'], 'favorite':True,
             'notes':'Mi nota', 'photo_data_url':'data:image/png;base64,saved',
             'generation_source':'local_recipe_catalog'}
    HomeFoodStore._upgrade_installed_recipe(saved)
    assert saved['id'] == 'kept' and saved['favorite']
    assert saved['notes'] == 'Mi nota' and saved['photo_data_url'].endswith('saved')
    assert saved['category'] == 'breakfast'
    assert '63 °C' not in ' '.join(saved['steps'])
    assert 'claras' in ' '.join(saved['steps'])
    assert saved['source_context'] and saved['editorial_revision']
    imported = {**saved, 'generation_source':'imported_url', 'steps':['Mi método propio']}
    before = deepcopy(imported)
    HomeFoodStore._upgrade_installed_recipe(imported)
    assert imported == before


def test_unknown_recipe_never_silently_becomes_chicken():
    with pytest.raises(ValueError, match='coincida'):
        generate_local_recipe('Injera etíope tradicional', {'profile':{}})


def test_only_reviewed_duplicates_are_recovered():
    rows = local_recipe_catalog({'profile':{}})
    titles = [row['title'] for row in rows]
    assert len(titles) == len(set(titles))
    assert sum(row.get('editorial_status') != 'needs_canonical_review' and row.get('audience') != 'pet' for row in rows) >= 59
    assert exact_local_recipe('Avena nocturna con frutas')['category'] == 'breakfast'
    assert any(row.get('editorial_status') == 'needs_canonical_review' for row in rows)


def test_ui_has_all_filter_and_no_unbacked_video_promises():
    script = Path('assets/roxy_list.js').read_text()
    assert "recipeFilter==='all'" in script
    assert '!available.has(id)' in script
    assert 'El video se preparará automáticamente al comenzar' not in script
    assert 'Cuando empieces a cocinar, Roxy preparará' not in script
