"""Memory checkpoint MVP — persist in Scheme B snapshot and restore."""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "memcp.db"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("QDRANT_ENABLED", "false")
    from app.config import get_settings
    from app.layer1_foundation.factory import get_llm
    get_settings.cache_clear()
    get_llm.cache_clear()
    import app.layer6_persistence.sqlite_db as sqlite_db
    import app.layer6_persistence.event_store as event_store
    import app.layer6_persistence.users as users
    if sqlite_db._CONN is not None:
        try:
            sqlite_db._CONN.close()
        except Exception:
            pass
        sqlite_db._CONN = None
    users._SCHEMA_READY = False
    event_store._SCHEMA_READY = False


def test_checkpoint_selects_recent_and_important():
    from app.layer3_agents.memory import MemoryStore

    store = MemoryStore(session_id="mem_test")
    for i in range(30):
        store.add("a1", "observation", f"普通记忆 {i}", importance=0.2)
    store.add("a1", "plan", "打开城门的计划", importance=0.4)
    store.add("a1", "belief", "守军不可靠", importance=0.3)
    store.add("a1", "observation", "看见火光", importance=0.95)

    cp = store.build_checkpoint(revision=3)
    assert cp["schema_version"] == 1
    assert cp["content_sha256"]
    assert cp["item_count"] >= 3
    kinds = {i["kind"] for i in cp["items"]}
    assert "plan" in kinds
    assert "belief" in kinds
    texts = " ".join(i["content"] for i in cp["items"])
    assert "看见火光" in texts

    other = MemoryStore(session_id="mem_test2")
    n = other.hydrate_from_checkpoint(cp)
    assert n == cp["item_count"]
    assert len(other.all()) == cp["item_count"]
    assert any("看见火光" in m.content for m in other.all())
    assert any(m.kind == "plan" for m in other.all())


def test_snapshot_roundtrip_restores_memory(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.session import create_session, _SESSIONS
    from app.session_persist import (
        force_save_snapshot, restore_session, SNAPSHOT_VERSION, persistable_snapshot,
    )
    from app.layer6_persistence.event_store import EventStore

    _SESSIONS.clear()
    sess = asyncio.run(create_session(
        "ancient", category_key="official", variant_key="student",
    ))
    pid = sess.primary_player_id
    assert pid

    # Seed a rich memory set.
    for i in range(20):
        sess.memory.add(pid, "observation", f"街景观察 {i}", importance=0.3)
    sess.memory.add(pid, "dialogue", "与商贾攀谈市价", importance=0.55)
    sess.memory.add(pid, "plan", "明日前往东市", importance=0.5)
    sess.memory.add(pid, "observation", "城门即将关闭", importance=0.9)
    seeded = [m.id for m in sess.memory.all()]
    assert len(seeded) >= 23

    snap = persistable_snapshot(sess)
    assert snap["snapshot_version"] == SNAPSHOT_VERSION == 2
    assert snap["memory"]["item_count"] >= 4
    assert snap["memory"]["content_sha256"]
    checkpoint_ids = {i["id"] for i in snap["memory"]["items"]}

    force_save_snapshot(sess)
    hit = EventStore(sess.id).latest_snapshot()
    assert hit is not None
    assert hit[1]["memory"]["item_count"] == snap["memory"]["item_count"]

    sid = sess.id
    _SESSIONS.clear()
    restored = restore_session(sid)
    assert restored is not None
    restored_ids = {m.id for m in restored.memory.all()}
    # ≥90% of checkpointed items must survive.
    overlap = checkpoint_ids & restored_ids
    ratio = len(overlap) / max(1, len(checkpoint_ids))
    assert ratio >= 0.9, f"restore ratio {ratio:.2%} < 90%"
    texts = " ".join(m.content for m in restored.memory.all())
    assert "城门即将关闭" in texts
    assert "明日前往东市" in texts
    # Recent buffer usable after restore.
    recent = restored.memory.recent_for(pid, limit=5)
    assert len(recent) >= 1


def test_content_truncation_and_hydrate_idempotent():
    from app.layer3_agents.memory import (
        MemoryStore, MEMORY_CHECKPOINT_CONTENT_MAX,
    )

    store = MemoryStore(session_id="trunc")
    long = "甲" * (MEMORY_CHECKPOINT_CONTENT_MAX + 500)
    store.add("a1", "observation", long, importance=0.9)
    cp = store.build_checkpoint()
    assert len(cp["items"]) == 1
    assert len(cp["items"][0]["content"]) <= MEMORY_CHECKPOINT_CONTENT_MAX
    assert cp["items"][0]["content"].endswith("…")

    other = MemoryStore(session_id="trunc2")
    n1 = other.hydrate_from_checkpoint(cp)
    n2 = other.hydrate_from_checkpoint(cp)
    assert n1 == 1
    assert n2 == 0  # same ids skipped
    assert len(other.all()) == 1


def test_checksum_mismatch_still_hydrates():
    from app.layer3_agents.memory import MemoryStore

    store = MemoryStore(session_id="badsum")
    store.add("a1", "observation", " intact memory ", importance=0.9)
    cp = store.build_checkpoint()
    cp["content_sha256"] = "0" * 64  # corrupt

    other = MemoryStore(session_id="badsum2")
    n = other.hydrate_from_checkpoint(cp)
    assert n == 1
    assert "intact memory" in other.all()[0].content


def test_old_low_importance_dropped_beyond_recent_k():
    from app.layer3_agents.memory import MemoryStore

    store = MemoryStore(session_id="drop")
    store.add("a1", "observation", "古老低重要度", importance=0.1)
    # Force older timestamp so it falls outside recent window after many adds.
    store._items[0].ts = 1.0
    for i in range(120):
        store.add("a1", "observation", f"新近 {i}", importance=0.2)

    cp = store.build_checkpoint(recent_k=100)
    texts = [i["content"] for i in cp["items"]]
    assert "古老低重要度" not in texts
    assert any(t.startswith("新近") for t in texts)


def test_multi_actor_recent_kept():
    from app.layer3_agents.memory import MemoryStore

    store = MemoryStore(session_id="multi")
    store.add("alice", "observation", "alice-only-note", importance=0.2)
    store.add("bob", "observation", "bob-only-note", importance=0.2)
    for i in range(50):
        store.add("carol", "observation", f"carol {i}", importance=0.2)
    cp = store.build_checkpoint(recent_k=10)
    texts = " ".join(i["content"] for i in cp["items"])
    assert "alice-only-note" in texts
    assert "bob-only-note" in texts


def test_v1_snapshot_without_memory_still_restores(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.session import create_session, _SESSIONS
    from app.session_persist import persistable_snapshot, restore_session
    from app.layer6_persistence.event_store import EventStore

    _SESSIONS.clear()
    sess = asyncio.run(create_session(
        "ancient", category_key="official", variant_key="student",
    ))
    pid = sess.primary_player_id
    sess.memory.add(pid, "observation", "不应出现在 v1 快照", importance=0.9)
    snap = persistable_snapshot(sess)
    # Downgrade to v1 without memory field (legacy Scheme B).
    legacy = {k: v for k, v in snap.items() if k != "memory"}
    legacy["snapshot_version"] = 1
    sid = sess.id
    EventStore(sid).save_snapshot(sess.world.clock.tick, legacy)
    _SESSIONS.clear()

    restored = restore_session(sid)
    assert restored is not None
    assert restored.primary_player_id == pid
    # No checkpoint → empty buffer (not a failure).
    assert len(restored.memory.all()) == 0
    # Soft-upgrade writes may bump version later; room must be playable.
    assert restored.id == sid


def test_restored_memory_survives_further_step(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.session import create_session, _SESSIONS, step
    from app.session_persist import force_save_snapshot, restore_session

    _SESSIONS.clear()
    sess = asyncio.run(create_session(
        "ancient", category_key="official", variant_key="student",
    ))
    pid = sess.primary_player_id
    sess.memory.add(pid, "plan", "探访驿站", importance=0.6)
    force_save_snapshot(sess)
    sid = sess.id
    _SESSIONS.clear()

    restored = restore_session(sid)
    assert any(m.content == "探访驿站" for m in restored.memory.all())
    page = asyncio.run(step(restored, player_id=pid, player_input="按计划前往驿站。"))
    assert page is not None
    # Prior plan still present after another narrative step.
    assert any(m.content == "探访驿站" for m in restored.memory.all())
