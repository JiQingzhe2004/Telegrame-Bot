from bot.runtime_state_store import MemoryStateStore, create_state_store


def test_memory_state_store_persistent_dict_round_trip():
    store = MemoryStateStore()
    session = store.persistent_dict("user:42", ttl_seconds=60)
    session["recent_chat_id"] = 1001
    session["step"] = "pay"

    loaded = store.get_json("user:42")
    assert loaded == {"recent_chat_id": 1001, "step": "pay"}


def test_memory_state_store_idempotency_and_lock():
    store = MemoryStateStore()

    assert store.set_if_absent("idem:test", "1", ttl_seconds=10) is True
    assert store.set_if_absent("idem:test", "1", ttl_seconds=10) is False

    token = store.acquire_lock("job:test", ttl_seconds=10)
    assert token is not None
    assert store.acquire_lock("job:test", ttl_seconds=10) is None
    store.release_lock("job:test", token)
    assert store.acquire_lock("job:test", ttl_seconds=10) is not None


def test_create_state_store_falls_back_to_memory():
    store = create_state_store("", namespace="tmbot", source="fallback")
    assert getattr(store, "mode", "") == "memory"
    assert getattr(store, "source", "") == "fallback"
