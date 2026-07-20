import os
from pathlib import Path

from tools import video_learning_ingest as ingest


def test_default_sources_do_not_implicitly_scan_external_volumes(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ROXY_VIDEO_SOURCES", raising=False)
    monkeypatch.setattr(ingest.Path, "home", lambda: tmp_path)

    sources = ingest.default_sources()

    assert sources
    assert all(str(path).startswith(str(tmp_path)) for path in sources)
    assert all(not str(path).startswith("/Volumes/") for path in sources)


def test_default_sources_accept_explicit_external_configuration(tmp_path: Path, monkeypatch):
    external = tmp_path / "mounted" / "videos"
    local = tmp_path / "Downloads"
    monkeypatch.setenv("ROXY_VIDEO_SOURCES", os.pathsep.join([str(local), str(external)]))

    assert ingest.default_sources() == [local, external]


def test_video_archive_dir_is_explicit_only(tmp_path: Path):
    assert ingest.configured_archive_dir({}) is None
    assert ingest.configured_archive_dir({"ROXY_VIDEO_ARCHIVE_DIR": "  "}) is None
    assert ingest.configured_archive_dir({"ROXY_VIDEO_ARCHIVE_DIR": str(tmp_path)}) == tmp_path


def test_detects_learning_video_keywords(tmp_path: Path):
    video = tmp_path / "11-09 MASTERCLASS DE MEDIAS MOVILES.mp4"
    video.write_bytes(b"fake")
    timing_video = tmp_path / "04-07-Clase Timinng 1-Min 07 Abril 2026.mp4"
    timing_video.write_bytes(b"fake")
    trimestral_video = tmp_path / "06-02-Clase Trimestral 02 Junio 2026.mp4"
    trimestral_video.write_bytes(b"fake")
    support_video = tmp_path / "05-20-Soporte Webull 20 Mayo 2026.mp4"
    support_video.write_bytes(b"fake")
    operative_video = tmp_path / "06-08-Operativa 08 Junio 2026.mp4"
    operative_video.write_bytes(b"fake")
    random_video = tmp_path / "birthday.mov"
    random_video.write_bytes(b"fake")

    assert ingest.looks_like_learning_video(video)
    assert ingest.looks_like_learning_video(timing_video)
    assert ingest.looks_like_learning_video(trimestral_video)
    assert ingest.looks_like_learning_video(support_video)
    assert ingest.looks_like_learning_video(operative_video)
    assert not ingest.looks_like_learning_video(random_video)
    assert ingest.looks_like_learning_video(random_video, allow_all=True)


def test_iter_video_files_respects_roxy_folder_allow_all(tmp_path: Path):
    source = tmp_path / "Roxy trading"
    source.mkdir()
    clip = source / "clase privada.mov"
    clip.write_bytes(b"fake")
    ignored = source / "notes.txt"
    ignored.write_text("not a video")

    found = ingest.iter_video_files([source])

    assert found == [clip.resolve()]


def test_detects_learning_material_keywords(tmp_path: Path):
    pdf = tmp_path / "VWAP-1.pdf"
    pdf.write_bytes(b"%PDF fake")
    economic = tmp_path / "Economic Cycle.pdf"
    economic.write_bytes(b"%PDF fake")
    orders = tmp_path / "Lecture+8+-+Orders+Driving+Prices+(Level1+-+Level2+-+Time+and+Sales).pdf"
    orders.write_bytes(b"%PDF fake")
    risk = tmp_path / "Lecture+23+-+Risk+Management.pdf"
    risk.write_bytes(b"%PDF fake")
    personal = tmp_path / "ID Cards Insured.pdf"
    personal.write_bytes(b"%PDF fake")

    assert ingest.looks_like_learning_material(pdf)
    assert ingest.looks_like_learning_material(economic)
    assert ingest.looks_like_learning_material(orders)
    assert ingest.looks_like_learning_material(risk)
    assert not ingest.looks_like_learning_material(personal)
    assert ingest.looks_like_learning_material(personal, allow_all=True)


def test_rejects_project_runtime_materials_even_in_roxy_folder(tmp_path: Path):
    runtime_file = tmp_path / "RoxyTrading" / "requirements.txt"
    runtime_file.parent.mkdir()
    runtime_file.write_text("streamlit\n")
    report_file = tmp_path / "RoxyTrading" / "weekly_report_20260609_090040.txt"
    report_file.write_text("report")

    assert not ingest.looks_like_learning_material(runtime_file, allow_all=True)
    assert not ingest.looks_like_learning_material(report_file, allow_all=True)


def test_iter_material_files_ignores_unrelated_roxyenterprise_project(tmp_path: Path):
    source = tmp_path / "Desktop"
    unrelated = source / "RoxyEnterprise" / "assets" / "documents" / "templates"
    unrelated.mkdir(parents=True)
    contract = unrelated / "engagement_letter.txt"
    contract.write_text("market services engagement template")
    study = source / "Market Efficiency.pdf"
    study.write_bytes(b"%PDF fake")

    found = ingest.iter_material_files([source])

    assert found == [study.resolve()]


def test_iter_material_files_respects_keywords(tmp_path: Path):
    source = tmp_path / "Downloads"
    source.mkdir()
    pdf = source / "Dark Pools.pdf"
    pdf.write_bytes(b"%PDF fake")
    ignored = source / "family-photo.jpg"
    ignored.write_bytes(b"jpg")

    found = ingest.iter_material_files([source])

    assert found == [pdf.resolve()]


def test_iter_video_files_ignores_partial_download_dirs(tmp_path: Path):
    source = tmp_path / "Downloads"
    partial = source / "06-05-Rebote en Media.mp4.download"
    partial.mkdir(parents=True)
    unfinished = partial / "06-05-Rebote en Media.mp4"
    unfinished.write_bytes(b"partial")
    finished = source / "05-26-Cruces de Medias Moviles.mp4"
    finished.write_bytes(b"fake")

    found = ingest.iter_video_files([source])

    assert found == [finished.resolve()]


def test_iter_video_files_ignores_download_marker_before_video_suffix(tmp_path: Path):
    source = tmp_path / "Roxy trading"
    source.mkdir()
    partial = source / "03-11-Operativa 11 Marzo 2026.mp4-2.download.mp4"
    partial.write_bytes(b"partial")
    finished = source / "03-11-Operativa 11 Marzo 2026.mp4"
    finished.write_bytes(b"complete")

    found = ingest.iter_video_files([source])

    assert found == [finished.resolve()]
    assert not ingest.looks_like_learning_video(partial, allow_all=True)


def test_process_text_material_creates_notes_and_manifest(tmp_path: Path):
    source = tmp_path / "Strategy-Types-1.txt"
    source.write_text("Trend analysis, VWAP, liquidity, short squeeze, pair trading and hedging.")

    manifest = ingest.process_material(source, tmp_path / "training")

    assert manifest["material_type"] == "txt"
    assert manifest["text_chars"] > 0
    assert "Ruptura o quiebre" not in manifest["topics"]
    notes = Path(manifest["notes_path"]).read_text()
    assert "Analisis de material de estudio" in notes
    assert "liquidez/VWAP" in notes


def test_build_notes_extracts_operable_media_rules():
    ocr = """
    USO DE LAS MEDIAS MOVILES
    CANAL ALCISTA DONDE SMA DE 20 Y 40 SON PISOS
    TENDENCIA DE LARGO PLAZO CONFIRMADA SMA 200
    QUIEBRE DE M200
    FUERZA INVERSA ENTRE MEDIAS
    """

    notes = ingest.build_notes(Path("/tmp/masterclass.mp4"), {"duration_minutes": 93.1, "width": 1366, "height": 768}, ocr)

    assert "Medias moviles" in notes
    assert "SMA20/SMA40" in notes
    assert "SMA200" in notes
    assert "No operar una media aislada" in notes
    assert "15m" in notes and "1h/4h" in notes


def test_update_index_dedupes_by_source(tmp_path: Path):
    item = {
        "source_path": "/tmp/video.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "identity": {"fingerprint": "abc"},
        "topics": ["Medias moviles"],
        "target_dir": str(tmp_path / "video"),
    }
    newer = dict(item)
    newer["processed_at"] = "2026-06-10T00:01:00+00:00"

    index = ingest.update_index(tmp_path, [item])
    index = ingest.update_index(tmp_path, [newer])

    assert len(index["videos"]) == 1
    assert index["videos"][0]["processed_at"] == newer["processed_at"]


def test_update_index_tracks_materials_separately(tmp_path: Path):
    material = {
        "source_path": "/tmp/VWAP.pdf",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "identity": {"fingerprint": "mat"},
        "topics": ["Medias moviles"],
        "target_dir": str(tmp_path / "vwap"),
    }

    index = ingest.update_index(tmp_path, [], [material])

    assert index["videos"] == []
    assert len(index["materials"]) == 1
    assert index["materials"][0]["source_path"] == "/tmp/VWAP.pdf"


def test_update_index_recovers_existing_video_manifest(tmp_path: Path):
    target = tmp_path / "video_a"
    target.mkdir()
    manifest = {
        "source_path": "/tmp/a.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "identity": {"fingerprint": "abc"},
        "topics": ["Medias moviles"],
        "target_dir": str(target),
    }
    (target / "manifest.json").write_text(ingest.json.dumps(manifest))

    index = ingest.update_index(tmp_path, [])

    assert len(index["videos"]) == 1
    assert index["videos"][0]["source_path"] == "/tmp/a.mp4"
    assert index["materials"] == []


def test_update_index_ignores_partial_source_manifest(tmp_path: Path):
    target = tmp_path / "partial_video"
    target.mkdir()
    manifest = {
        "source_path": "/tmp/lesson.mp4-2.download.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "identity": {"fingerprint": "partial"},
        "topics": ["Medias moviles"],
        "target_dir": str(target),
    }
    (target / "manifest.json").write_text(ingest.json.dumps(manifest))

    index = ingest.update_index(tmp_path, [])

    assert index["videos"] == []
    assert index["materials"] == []


def test_update_index_removes_existing_partial_source_entry(tmp_path: Path):
    target = tmp_path / "partial_video"
    target.mkdir()
    partial = {
        "source_path": "/tmp/lesson.mp4-2.download.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "identity": {"fingerprint": "partial"},
        "topics": ["Medias moviles"],
        "target_dir": str(target),
    }
    (tmp_path / "video_learning_index.json").write_text(
        ingest.json.dumps({"updated_at": "2026-06-10T00:00:00+00:00", "videos": [partial], "materials": []})
    )

    index = ingest.update_index(tmp_path, [])

    assert index["videos"] == []


def test_cleanup_partial_artifacts_removes_unindexed_partial_target(tmp_path: Path):
    target = tmp_path / "partial_video"
    target.mkdir()
    (target / "frame.jpg").write_bytes(b"x" * 1024)
    manifest = {
        "source_path": "/tmp/lesson.mp4-2.download.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "target_dir": str(target),
    }
    (target / "manifest.json").write_text(ingest.json.dumps(manifest))
    index = {"videos": [], "materials": []}

    result = ingest.cleanup_partial_artifacts(tmp_path, index)

    assert result["removed_count"] == 1
    assert result["reclaimed_bytes"] > 0
    assert not target.exists()


def test_cleanup_partial_artifacts_skips_indexed_partial_target(tmp_path: Path):
    target = tmp_path / "partial_video"
    target.mkdir()
    manifest = {
        "source_path": "/tmp/lesson.mp4-2.download.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "target_dir": str(target),
    }
    (target / "manifest.json").write_text(ingest.json.dumps(manifest))
    index = {"videos": [manifest], "materials": []}

    result = ingest.cleanup_partial_artifacts(tmp_path, index)

    assert result["removed_count"] == 0
    assert result["skipped_count"] == 1
    assert target.exists()


def test_run_once_cleanup_partial_artifacts_removes_generated_partial_dir(tmp_path: Path):
    output = tmp_path / "training"
    target = output / "partial_video"
    target.mkdir(parents=True)
    manifest = {
        "source_path": "/tmp/lesson.mp4-2.download.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "target_dir": str(target),
    }
    (target / "manifest.json").write_text(ingest.json.dumps(manifest))
    source = tmp_path / "empty_source"
    source.mkdir()
    args = ingest.argparse.Namespace(
        output=str(output),
        source=[str(source)],
        max_depth=1,
        force=False,
        every_seconds=300,
        transcribe=False,
        model_size="tiny",
        language="es",
        limit=0,
        archive_dir="",
        archive_indexed=False,
        idle_review=False,
        reconcile_index_only=True,
        cleanup_partial_artifacts=True,
    )

    result = ingest.run_once(args)

    assert result["partial_artifacts_removed"] == 1
    assert result["partial_artifacts_reclaimed_mb"] >= 0
    assert not target.exists()


def test_run_once_reconciles_manifest_without_reprocessing(tmp_path: Path):
    output = tmp_path / "training"
    target = output / "video_a"
    target.mkdir(parents=True)
    manifest = {
        "source_path": "/tmp/a.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "identity": {"fingerprint": "abc"},
        "topics": ["Medias moviles"],
        "target_dir": str(target),
    }
    (target / "manifest.json").write_text(ingest.json.dumps(manifest))
    source = tmp_path / "empty_source"
    source.mkdir()
    args = ingest.argparse.Namespace(
        output=str(output),
        source=[str(source)],
        max_depth=1,
        force=False,
        every_seconds=300,
        transcribe=False,
        model_size="tiny",
        language="es",
        limit=0,
        archive_dir="",
        archive_indexed=False,
        idle_review=False,
        reconcile_index_only=False,
        cleanup_partial_artifacts=False,
    )

    result = ingest.run_once(args)

    assert result["processed"] == 0
    assert result["manifest_reconciled"] == 1
    assert len(result["index"]["videos"]) == 1
    assert (output / "ROXY_LEARNING_SYNC.md").exists()


def test_run_once_reconcile_index_only_skips_source_scans(tmp_path: Path, monkeypatch):
    output = tmp_path / "training"
    target = output / "video_a"
    target.mkdir(parents=True)
    manifest = {
        "source_path": "/tmp/a.mp4",
        "processed_at": "2026-06-10T00:00:00+00:00",
        "identity": {"fingerprint": "abc"},
        "topics": ["Medias moviles"],
        "target_dir": str(target),
    }
    (target / "manifest.json").write_text(ingest.json.dumps(manifest))
    source = tmp_path / "source"
    source.mkdir()

    def fail_scan(*args, **kwargs):
        raise AssertionError("source scan should be skipped")

    monkeypatch.setattr(ingest, "iter_video_files", fail_scan)
    monkeypatch.setattr(ingest, "iter_material_files", fail_scan)
    args = ingest.argparse.Namespace(
        output=str(output),
        source=[str(source)],
        max_depth=1,
        force=False,
        every_seconds=300,
        transcribe=False,
        model_size="tiny",
        language="es",
        limit=0,
        archive_dir="",
        archive_indexed=False,
        idle_review=False,
        reconcile_index_only=True,
        cleanup_partial_artifacts=False,
    )

    result = ingest.run_once(args)

    assert result["found"] == 0
    assert result["materials_found"] == 0
    assert result["manifest_reconciled"] == 1
    assert len(result["index"]["videos"]) == 1


def test_run_once_publishes_index_after_each_processed_video(tmp_path: Path, monkeypatch):
    output = tmp_path / "training"
    source = tmp_path / "source"
    source.mkdir()
    first = source / "01-Medias Moviles.mp4"
    second = source / "02-Medias Moviles.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    calls = []

    monkeypatch.setattr(ingest, "iter_video_files", lambda *_args, **_kwargs: [first, second])
    monkeypatch.setattr(ingest, "iter_material_files", lambda *_args, **_kwargs: [])

    def fake_process_video(path: Path, out_root: Path, **_kwargs):
        calls.append(path)
        if path == second:
            raise RuntimeError("processing interrupted")
        target = out_root / "first"
        target.mkdir(parents=True)
        manifest = {
            "source_path": str(path),
            "processed_at": "2026-06-10T00:00:00+00:00",
            "identity": {"fingerprint": "first"},
            "topics": ["Medias moviles"],
            "target_dir": str(target),
        }
        (target / "manifest.json").write_text(ingest.json.dumps(manifest))
        return manifest

    monkeypatch.setattr(ingest, "process_video", fake_process_video)
    args = ingest.argparse.Namespace(
        output=str(output),
        source=[str(source)],
        max_depth=1,
        force=False,
        every_seconds=300,
        transcribe=False,
        model_size="tiny",
        language="es",
        limit=0,
        archive_dir="",
        archive_indexed=False,
        idle_review=False,
        reconcile_index_only=False,
        cleanup_partial_artifacts=False,
    )

    try:
        ingest.run_once(args)
    except RuntimeError as exc:
        assert str(exc) == "processing interrupted"
    else:
        raise AssertionError("expected processing interruption")

    index = ingest.json.loads((output / "video_learning_index.json").read_text())
    assert calls == [first, second]
    assert len(index["videos"]) == 1
    assert index["videos"][0]["source_path"] == str(first)


def test_archive_video_source_accepts_completed_cross_device_move_race(tmp_path: Path, monkeypatch):
    source = tmp_path / "Downloads" / "03-25-Masterclass EMA 9.mp4"
    archive = tmp_path / "Archive"
    source.parent.mkdir()
    source.write_bytes(b"video-bytes")

    def fake_move(src: str, dst: str) -> str:
        Path(dst).write_bytes(Path(src).read_bytes())
        Path(src).unlink()
        raise FileNotFoundError(src)

    monkeypatch.setattr(ingest.shutil, "move", fake_move)

    target = ingest.archive_video_source(source, archive)

    assert target == archive / source.name
    assert target.read_bytes() == b"video-bytes"
    assert not source.exists()


def test_archive_video_source_skips_permission_denied_without_deleting_source(tmp_path: Path, monkeypatch):
    source = tmp_path / "Natalia" / "Crear y modificar el watchlist.mp4"
    archive = tmp_path / "Archive"
    source.parent.mkdir()
    source.write_bytes(b"video-bytes")

    def fake_move(src: str, dst: str) -> str:
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(ingest.shutil, "move", fake_move)

    target = ingest.archive_video_source(source, archive)

    assert target is None
    assert source.exists()
    assert source.read_bytes() == b"video-bytes"


def test_idle_learning_review_summarizes_existing_topics():
    index = {
        "videos": [
            {"source_path": "/tmp/a.mp4", "processed_at": "2026-06-12", "topics": ["Medias moviles", "Timing de entrada"]},
            {"source_path": "/tmp/b.mp4", "processed_at": "2026-06-11", "topics": ["Medias moviles", "Canales y tendencias"]},
        ],
        "materials": [
            {"source_path": "/tmp/VWAP.pdf", "processed_at": "2026-06-10", "topics": ["Opciones"]},
        ],
    }

    review = ingest.idle_learning_review(index)

    assert review["video_count"] == 2
    assert review["material_count"] == 1
    assert review["topic_counts"]["Medias moviles"] == 2
    assert any(item["area"] == "Medias moviles" for item in review["strategy_actions"])
    assert any(item["area"] == "Timing" for item in review["strategy_actions"])
    assert any(item["area"] == "Opciones" for item in review["strategy_actions"])


def test_write_idle_learning_review_creates_markdown_and_json(tmp_path: Path):
    index = {
        "videos": [
            {
                "source_path": "/tmp/masterclass.mp4",
                "processed_at": "2026-06-12",
                "topics": ["Canales y tendencias"],
                "notes_path": "/tmp/notes.md",
            }
        ]
    }

    review_path = ingest.write_idle_learning_review(tmp_path, index)

    assert review_path.exists()
    assert (tmp_path / "idle_learning_review.json").exists()
    body = review_path.read_text()
    assert "Roxy Idle Learning Review" in body
    assert "Canales y tendencias" in body


def test_build_teacher_playbook_turns_topics_into_operating_rules():
    index = {
        "videos": [
            {
                "source_path": "/tmp/03-25-Masterclass EMA 9.mp4",
                "topics": ["Medias moviles", "Timing de entrada"],
            },
            {
                "source_path": "/tmp/03-09-Canales y Tendencias.mp4",
                "topics": ["Canales y tendencias"],
            },
        ],
        "materials": [
            {
                "source_path": "/tmp/Risk Management.pdf",
                "topics": ["Riesgo", "Check list y no negociables"],
            }
        ],
    }

    playbook = ingest.build_teacher_playbook(index)

    assert playbook["source_counts"]["videos"] == 2
    assert playbook["source_counts"]["materials"] == 1
    assert playbook["topic_counts"]["Medias moviles"] == 1
    assert any(rule["id"] == "ma_alignment" for rule in playbook["strategy_rules"])
    assert any(rule["id"] == "timing_precision" for rule in playbook["strategy_rules"])
    assert any(item["id"] == "no_plan" for item in playbook["anti_patterns"])
    assert "Entrada, stop, target, R/R y razon visibles." in playbook["opportunity_checklist"]


def test_write_teacher_playbook_creates_markdown_and_json(tmp_path: Path):
    index = {
        "videos": [
            {
                "source_path": "/tmp/05-26-Cruces de Medias Moviles.mp4",
                "topics": ["Medias moviles"],
            }
        ],
        "materials": [],
    }

    path = ingest.write_teacher_playbook(tmp_path, index)

    assert path.exists()
    assert (tmp_path / "roxy_teacher_playbook.json").exists()
    body = path.read_text()
    assert "Roxy Teacher Playbook" in body
    assert "Alineacion de medias antes de entrar" in body


def test_parse_args_defaults_to_35_minute_watch_interval(monkeypatch):
    monkeypatch.setattr(ingest, "argparse", ingest.argparse)
    monkeypatch.setattr("sys.argv", ["video_learning_ingest.py"])

    args = ingest.parse_args()

    assert args.interval == 2100
