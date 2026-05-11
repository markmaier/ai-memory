import json
import logging
import threading
from copy import deepcopy
from typing import Any, Callable, Dict

from mem0 import Memory

_state_lock = threading.RLock()
_current_config: Dict[str, Any] = {}
_memory_instances: dict[str, Memory] = {}
_memory_lock = threading.Lock()
_session_factory: Callable | None = None


def set_session_factory(factory: Callable) -> None:
    global _session_factory
    _session_factory = factory


def _load_overrides() -> Dict[str, Any]:
    try:
        if _session_factory is None:
            return {}
        from models import Settings

        session = _session_factory()
        try:
            row = session.get(Settings, "config_overrides")
            if row is None:
                return {}
            return json.loads(row.value)
        finally:
            session.close()
    except Exception:
        return {}


def _save_overrides(overrides: Dict[str, Any]) -> None:
    try:
        if _session_factory is None:
            return
        from models import Settings
        from sqlalchemy.dialects.postgresql import insert

        session = _session_factory()
        try:
            serialized = json.dumps(overrides)
            stmt = (
                insert(Settings)
                .values(key="config_overrides", value=serialized)
                .on_conflict_do_update(
                    index_elements=[Settings.key],
                    set_={"value": serialized},
                )
            )
            session.execute(stmt)
            session.commit()
        finally:
            session.close()
    except Exception:
        logging.warning("Failed to persist config overrides to database", exc_info=True)


def _merge_config(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)

    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            # Different providers have incompatible config schemas.
            if "provider" in value and value.get("provider") != merged[key].get("provider"):
                merged[key] = deepcopy(value)
            else:
                merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value

    return merged


def initialize_state(default_config: Dict[str, Any]) -> None:
    global _current_config
    with _state_lock:
        _current_config = deepcopy(default_config)
        overrides = _load_overrides()
        if overrides:
            _current_config = _merge_config(_current_config, overrides)
        with _memory_lock:
            _memory_instances.clear()


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    global _current_config
    with _state_lock:
        next_config = _merge_config(_current_config, updates)
        _current_config = next_config
        with _memory_lock:
            _memory_instances.clear()
        overrides = _load_overrides()
        overrides = _merge_config(overrides, updates)
        _save_overrides(overrides)
        return deepcopy(_current_config)


def get_current_config() -> Dict[str, Any]:
    with _state_lock:
        return deepcopy(_current_config)


def get_memory_instance() -> Memory:
    with _state_lock:
        if not _current_config:
            raise RuntimeError("Mem0 runtime has not been initialized.")
        default_collection_name = (
            _current_config.get("vector_store", {}).get("config", {}).get("collection_name")
        )
    if not isinstance(default_collection_name, str) or not default_collection_name:
        raise RuntimeError("Default collection_name is not configured.")

    return get_memory_for_project(default_collection_name)


def get_memory_for_project(collection_name: str) -> Memory:
    if not collection_name:
        raise ValueError("collection_name must be a non-empty string")

    cached = _memory_instances.get(collection_name)
    if cached is not None:
        return cached

    with _state_lock:
        if not _current_config:
            raise RuntimeError("Mem0 runtime has not been initialized.")
        project_config = deepcopy(_current_config)
        vector_store = project_config.setdefault("vector_store", {})
        vector_store_config = vector_store.setdefault("config", {})
        vector_store_config["collection_name"] = collection_name

        with _memory_lock:
            cached = _memory_instances.get(collection_name)
            if cached is not None:
                return cached

            memory = Memory.from_config(project_config)
            _memory_instances[collection_name] = memory
            return memory


def drop_memory_collection(collection_name: str) -> None:
    if not collection_name:
        return

    with _memory_lock:
        memory = _memory_instances.pop(collection_name, None)

    if memory is None:
        return

    delete_collection = getattr(memory, "delete_collection", None)
    if callable(delete_collection):
        try:
            delete_collection()
        except Exception:
            logging.warning(
                "Failed to drop memory collection from underlying store",
                exc_info=True,
                extra={"collection_name": collection_name},
            )
