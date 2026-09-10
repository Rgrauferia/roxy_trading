"""Exact photo previews: bounded transfer, stable caching, and safe failure."""

import base64
import concurrent.futures
import io
import os
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from roxy_os.home_recipe_photos import CARD_PHOTO_MAX_BYTES, RecipePhotoStore


def _store_photo(tmp_path, *, title="Exact food", approved=True, picture=None):
    store = RecipePhotoStore(tmp_path / "photos", built_in_root=tmp_path / "built-in")
    encoded = io.BytesIO()
    (picture or Image.new("RGB", (1024, 768), "green")).save(encoded, format="PNG")
    source = store.save_generated(title, base64.b64encode(encoded.getvalue()).decode(), approved=approved)
    return store, source


def test_card_is_small_exact_derivative_and_full_image_is_unchanged(tmp_path):
    picture = Image.effect_noise((1024, 1024), 90).convert("RGB")
    store, source = _store_photo(tmp_path, picture=picture)
    original = source.read_bytes()

    card, metadata = store.resolve_card("Exact food")

    assert card != source
    assert card.stat().st_size <= CARD_PHOTO_MAX_BYTES
    assert metadata["media_type"] == "image/webp"
    assert metadata["title"] == "Exact food" and metadata["approved"] is True
    with Image.open(card) as image:
        assert image.format == "WEBP" and max(image.size) <= 480
    assert store.resolve("Exact food")[0] == source
    assert source.read_bytes() == original


def test_card_applies_orientation_without_upscaling_or_embedded_metadata(tmp_path):
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    picture = Image.new("RGB", (100, 200), "blue")
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "Private metadata must not reach the derivative"
    picture.save(built_in / "pan-cubano.jpg", exif=exif)
    store = RecipePhotoStore(tmp_path / "photos", built_in_root=built_in)

    card, _metadata = store.resolve_card("Pan cubano")

    with Image.open(card) as image:
        assert image.size == (200, 100)
        assert not image.getexif()
        assert "exif" not in image.info
    assert b"Private metadata" not in card.read_bytes()


def test_card_cache_reuses_work_across_store_instances_and_threads(tmp_path, monkeypatch):
    store, _source = _store_photo(tmp_path)
    stores = [store, RecipePhotoStore(store.root, built_in_root=store.built_in_root)]
    calls = []
    original = RecipePhotoStore._card_image_bytes

    def counted(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(RecipePhotoStore, "_card_image_bytes", staticmethod(counted))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
        cards = list(workers.map(lambda index: stores[index % 2].resolve_card("Exact food")[0], range(16)))

    assert len(calls) == 1
    assert len(set(cards)) == 1
    assert not list(cards[0].parent.glob("*.tmp"))


def test_replacing_source_invalidates_preview_even_when_size_and_mtime_match(tmp_path):
    store, source = _store_photo(tmp_path)
    first = store.resolve_card("Exact food")[0]
    previous = source.stat()
    replacement = source.with_suffix(".replacement")
    replacement.write_bytes(source.read_bytes())
    os.utime(replacement, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    replacement.replace(source)

    second = store.resolve_card("Exact food")[0]

    assert source.stat().st_size == previous.st_size
    assert source.stat().st_mtime_ns == previous.st_mtime_ns
    assert second != first


def test_cached_card_never_bypasses_approval_quarantine_or_missing_original(tmp_path):
    store, source = _store_photo(tmp_path)
    assert store.resolve_card("Exact food")
    manifest = store._manifest()
    manifest["photos"][store._key("Exact food")]["approved"] = False
    store._save_manifest(manifest)
    assert store.resolve_card("Exact food") is None
    store.approve("Exact food")
    source.unlink()
    assert store.resolve_card("Exact food") is None
    assert store.resolve_card("Unrelated food") is None
    store, _source = _store_photo(tmp_path / "quarantine", title="Aderezo César")
    assert store.resolve_card("Aderezo César") is None


def test_corrupted_source_falls_back_to_its_original_without_another_photo(tmp_path):
    store, source = _store_photo(tmp_path)
    source.write_bytes(b"broken exact original")

    card, metadata = store.resolve_card("Exact food")

    assert card == source
    assert metadata["media_type"] == "image/png"
    assert not (store.root / "card-cache-v1").exists()


def test_corrupted_cached_preview_is_regenerated(tmp_path):
    store, _source = _store_photo(tmp_path)
    cached = store.resolve_card("Exact food")[0]
    cached.write_bytes(b"invalid preview")

    assert store.resolve_card("Exact food")[0] == cached
    with Image.open(cached) as image:
        assert image.format == "WEBP"


def test_low_storage_keeps_original_and_does_not_encode(tmp_path, monkeypatch):
    from roxy_os import home_recipe_photos

    store, source = _store_photo(tmp_path)
    monkeypatch.setattr(home_recipe_photos.shutil, "disk_usage", lambda _root: SimpleNamespace(free=1024))
    monkeypatch.setattr(store, "_card_image_bytes", lambda _path: (_ for _ in ()).throw(AssertionError("Must not encode")))

    assert store.resolve_card("Exact food")[0] == source


def test_atomic_cache_write_failure_keeps_original_and_cleans_temporary(tmp_path, monkeypatch):
    store, source = _store_photo(tmp_path)
    original = Path.replace

    def fail_preview_replace(path, target):
        if path.suffix == ".tmp" and path.parent.name == "card-cache-v1":
            raise OSError("synthetic disk failure")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", fail_preview_replace)

    assert store.resolve_card("Exact food")[0] == source
    assert not list((store.root / "card-cache-v1").glob("*.tmp"))


def test_source_changed_during_encode_does_not_publish_a_stale_preview(tmp_path, monkeypatch):
    store, source = _store_photo(tmp_path)
    original = store._card_image_bytes

    def replace_during_encode(path):
        result = original(path)
        path.write_bytes(b"changed exact original")
        return result

    monkeypatch.setattr(store, "_card_image_bytes", replace_during_encode)

    assert store.resolve_card("Exact food")[0] == source
    assert not (store.root / "card-cache-v1").exists()
