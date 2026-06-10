from pathlib import Path

from tools.move_parallels_vm_to_external import move_vm


def test_move_vm_blocks_when_parallels_is_running(tmp_path, monkeypatch):
    source = tmp_path / "Windows 11.pvm"
    target = tmp_path / "external" / "Windows 11.pvm"
    source.mkdir()
    monkeypatch.setattr("tools.move_parallels_vm_to_external.parallels_processes_running", lambda: ["123 prl_client_app"])

    result = move_vm(source, target)

    assert result["status"] == "blocked"
    assert source.exists()
    assert not target.exists()


def test_move_vm_moves_directory_and_leaves_symlink(tmp_path, monkeypatch):
    source = tmp_path / "Windows 11.pvm"
    target = tmp_path / "external" / "Windows 11.pvm"
    source.mkdir()
    (source / "config.pvs").write_text("vm")
    monkeypatch.setattr("tools.move_parallels_vm_to_external.parallels_processes_running", lambda: [])

    result = move_vm(source, target)

    assert result["status"] == "moved"
    assert source.is_symlink()
    assert Path(source.readlink()) == target
    assert (target / "config.pvs").read_text() == "vm"


def test_move_vm_refuses_existing_target(tmp_path, monkeypatch):
    source = tmp_path / "Windows 11.pvm"
    target = tmp_path / "external" / "Windows 11.pvm"
    source.mkdir()
    target.mkdir(parents=True)
    monkeypatch.setattr("tools.move_parallels_vm_to_external.parallels_processes_running", lambda: [])

    result = move_vm(source, target)

    assert result["status"] == "target_exists"
    assert source.exists()
