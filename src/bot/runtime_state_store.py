from __future__ import annotations

import json
import time
import uuid
from collections.abc import MutableMapping
from typing import Any

try:
    from redis import Redis
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore[assignment]


class PersistentJsonDict(dict):
    def __init__(self, initial: dict[str, Any], *, save_fn, delete_fn) -> None:
        super().__init__(initial)
        self._save_fn = save_fn
        self._delete_fn = delete_fn

    def _sync(self) -> None:
        if self:
            self._save_fn(dict(self))
        else:
            self._delete_fn()

    def __setitem__(self, key, value) -> None:  # type: ignore[override]
        super().__setitem__(key, value)
        self._sync()

    def __delitem__(self, key) -> None:  # type: ignore[override]
        super().__delitem__(key)
        self._sync()

    def clear(self) -> None:
        super().clear()
        self._sync()

    def pop(self, key, default=None):  # type: ignore[override]
        out = super().pop(key, default)
        self._sync()
        return out

    def popitem(self):  # type: ignore[override]
        out = super().popitem()
        self._sync()
        return out

    def update(self, *args, **kwargs) -> None:  # type: ignore[override]
        super().update(*args, **kwargs)
        self._sync()

    def setdefault(self, key, default=None):  # type: ignore[override]
        value = super().setdefault(key, default)
        self._sync()
        return value


class StateStore:
    def get_json(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int | None = None) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def set_if_absent(self, key: str, value: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    def acquire_lock(self, name: str, ttl_seconds: int) -> str | None:
        raise NotImplementedError

    def release_lock(self, name: str, token: str) -> None:
        raise NotImplementedError

    def get_cached_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        raise NotImplementedError

    def set_cached_json(self, key: str, value: dict[str, Any] | list[Any], ttl_seconds: int) -> None:
        raise NotImplementedError

    def delete_cached(self, key: str) -> None:
        raise NotImplementedError

    def persistent_dict(self, key: str, *, ttl_seconds: int | None = None) -> PersistentJsonDict:
        current = self.get_json(key) or {}
        return PersistentJsonDict(
            current,
            save_fn=lambda value: self.set_json(key, value, ttl_seconds=ttl_seconds),
            delete_fn=lambda: self.delete(key),
        )


class MemoryStateStore(StateStore):
    def __init__(self) -> None:
        self.mode = "memory"
        self.source = "fallback"
        self._json_data: dict[str, tuple[dict[str, Any], float | None]] = {}
        self._text_data: dict[str, tuple[str, float | None]] = {}
        self._cache_data: dict[str, tuple[dict[str, Any] | list[Any], float | None]] = {}
        self._locks: dict[str, tuple[str, float]] = {}

    @staticmethod
    def _expired(expires_at: float | None) -> bool:
        return expires_at is not None and expires_at <= time.time()

    def _cleanup_json(self, key: str) -> None:
        current = self._json_data.get(key)
        if current and self._expired(current[1]):
            self._json_data.pop(key, None)

    def _cleanup_text(self, key: str) -> None:
        current = self._text_data.get(key)
        if current and self._expired(current[1]):
            self._text_data.pop(key, None)

    def _cleanup_cache(self, key: str) -> None:
        current = self._cache_data.get(key)
        if current and self._expired(current[1]):
            self._cache_data.pop(key, None)

    def get_json(self, key: str) -> dict[str, Any] | None:
        self._cleanup_json(key)
        current = self._json_data.get(key)
        return dict(current[0]) if current else None

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int | None = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._json_data[key] = (dict(value), expires_at)

    def delete(self, key: str) -> None:
        self._json_data.pop(key, None)
        self._text_data.pop(key, None)

    def set_if_absent(self, key: str, value: str, ttl_seconds: int) -> bool:
        self._cleanup_text(key)
        if key in self._text_data:
            return False
        self._text_data[key] = (value, time.time() + ttl_seconds)
        return True

    def acquire_lock(self, name: str, ttl_seconds: int) -> str | None:
        current = self._locks.get(name)
        if current and current[1] > time.time():
            return None
        token = uuid.uuid4().hex
        self._locks[name] = (token, time.time() + ttl_seconds)
        return token

    def release_lock(self, name: str, token: str) -> None:
        current = self._locks.get(name)
        if current and current[0] == token:
            self._locks.pop(name, None)

    def get_cached_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        self._cleanup_cache(key)
        current = self._cache_data.get(key)
        if current is None:
            return None
        return json.loads(json.dumps(current[0], ensure_ascii=False))

    def set_cached_json(self, key: str, value: dict[str, Any] | list[Any], ttl_seconds: int) -> None:
        self._cache_data[key] = (json.loads(json.dumps(value, ensure_ascii=False)), time.time() + ttl_seconds)

    def delete_cached(self, key: str) -> None:
        self._cache_data.pop(key, None)


class RedisStateStore(StateStore):
    def __init__(self, redis_url: str, namespace: str = "tmbot") -> None:
        if Redis is None:
            raise RuntimeError("redis_client_not_installed")
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.namespace = namespace
        self.mode = "redis"
        self.source = "runtime_config"

    def _key(self, key: str) -> str:
        return f"{self.namespace}:{key}"

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self.client.get(self._key(key))
        if not raw:
            return None
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int | None = None) -> None:
        self.client.set(self._key(key), json.dumps(value, ensure_ascii=False), ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self.client.delete(self._key(key))

    def set_if_absent(self, key: str, value: str, ttl_seconds: int) -> bool:
        return bool(self.client.set(self._key(key), value, nx=True, ex=ttl_seconds))

    def acquire_lock(self, name: str, ttl_seconds: int) -> str | None:
        token = uuid.uuid4().hex
        success = self.client.set(self._key(f"lock:{name}"), token, nx=True, ex=ttl_seconds)
        return token if success else None

    def release_lock(self, name: str, token: str) -> None:
        key = self._key(f"lock:{name}")
        pipe = self.client.pipeline(True)
        while True:
            try:
                pipe.watch(key)
                if pipe.get(key) != token:
                    pipe.reset()
                    return
                pipe.multi()
                pipe.delete(key)
                pipe.execute()
                return
            except Exception:  # noqa: BLE001
                pipe.reset()
                return

    def get_cached_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        raw = self.client.get(self._key(f"cache:{key}"))
        if not raw:
            return None
        return json.loads(raw)

    def set_cached_json(self, key: str, value: dict[str, Any] | list[Any], ttl_seconds: int) -> None:
        self.client.set(self._key(f"cache:{key}"), json.dumps(value, ensure_ascii=False), ex=ttl_seconds)

    def delete_cached(self, key: str) -> None:
        self.client.delete(self._key(f"cache:{key}"))


def create_state_store(redis_url: str, namespace: str = "tmbot", *, source: str = "runtime_config") -> StateStore:
    if redis_url.strip():
        store = RedisStateStore(redis_url, namespace=namespace)
        store.source = source  # type: ignore[attr-defined]
        return store
    memory = MemoryStateStore()
    memory.source = "fallback"  # type: ignore[attr-defined]
    return memory
