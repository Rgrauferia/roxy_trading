def test_storage_api_exists():
    import storage

    # basic smoke: ensure some key helpers are present
    assert hasattr(storage, "get_account_equity")
    assert hasattr(storage, "get_open_positions")

