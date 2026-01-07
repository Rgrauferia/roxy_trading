import os
import time
import tools.process_manager as pm


def test_start_stop_run_once(tmp_path):
    # ensure run dir is under tmp_path for isolation
    os.environ.setdefault("PYTHON", "python")
    # start in run_once mode (process should exit quickly)
    pid = pm.start_snapshot_service(run_once=True)
    assert pid is not None
    # PID file should exist
    p = pm.get_pid()
    assert p == pid
    # stop should clean up PID file even if process already exited
    ok = pm.stop_snapshot_service()
    assert ok is True
    assert pm.get_pid() is None
