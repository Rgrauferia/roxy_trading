from pathlib import Path

import roxy_paths


def test_project_path_routes_runtime_directories_to_configured_roots(monkeypatch, tmp_path):
    roots = {
        "output": tmp_path / "runtime-output",
        "alerts": tmp_path / "runtime-alerts",
        "data": tmp_path / "runtime-data",
        "db": tmp_path / "runtime-db",
    }
    for name, root in roots.items():
        monkeypatch.setenv(roxy_paths.RUNTIME_DIRECTORY_ENV[name], str(root))

    assert roxy_paths.project_path("output/report.json") == roots["output"] / "report.json"
    assert roxy_paths.project_path("alerts/health.json") == roots["alerts"] / "health.json"
    assert roxy_paths.project_path("data/watchlists.json") == roots["data"] / "watchlists.json"
    assert roxy_paths.project_path("db/roxy.db") == roots["db"] / "roxy.db"


def test_project_path_keeps_packaged_assets_in_project(monkeypatch):
    for env_name in roxy_paths.RUNTIME_DIRECTORY_ENV.values():
        monkeypatch.delenv(env_name, raising=False)

    assert roxy_paths.project_path("assets/roxy_mobile.js") == roxy_paths.BASE_DIR / "assets/roxy_mobile.js"
    assert roxy_paths.project_path("data/macro_events.csv") == roxy_paths.BASE_DIR / "data/macro_events.csv"


def test_configured_dir_does_not_recurse_through_runtime_mapping(monkeypatch, tmp_path):
    monkeypatch.setenv("ROXY_DATA_DIR", str(tmp_path / "data"))

    assert roxy_paths.data_dir() == tmp_path / "data"
    assert roxy_paths.project_path(Path("data") / "state.json") == tmp_path / "data" / "state.json"
