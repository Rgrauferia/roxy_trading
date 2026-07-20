def test_storage_api_exists():
    import storage

    # basic smoke: ensure some key helpers are present
    assert hasattr(storage, "get_account_equity")
    assert hasattr(storage, "get_open_positions")


def test_simulated_trade_reads_can_be_scoped_by_user(tmp_path):
    import storage

    path = str(tmp_path / "roxy.db")
    storage.save_simulated_trade("alice", "AAPL", "BUY", 1, 100, path=path)
    storage.save_simulated_trade("bob", "MSFT", "BUY", 2, 200, path=path)

    alice = storage.get_simulated_trades(limit=10, path=path, user="alice")

    assert len(alice) == 1
    assert alice[0][2] == "alice"
    assert alice[0][3] == "AAPL"
