from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    ListNamespacesOp,
    MatchCondition,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)

from ..buffer import WarmMemoryBuffer
from ..scoring import ImportanceScorer, KeywordImportanceScorer


_FILTER_OPS = {
    "$eq": lambda a, b: a == b,
    "$ne": lambda a, b: a != b,
    "$gt": lambda a, b: a is not None and b is not None and a > b,
    "$gte": lambda a, b: a is not None and b is not None and a >= b,
    "$lt": lambda a, b: a is not None and b is not None and a < b,
    "$lte": lambda a, b: a is not None and b is not None and a <= b,
}


def _matches_filter(value: Mapping[str, Any], filter_spec: Mapping[str, Any] | None) -> bool:
    if not filter_spec:
        return True
    for field_name, condition in filter_spec.items():
        actual = value.get(field_name)
        if isinstance(condition, Mapping):
            for op_name, expected in condition.items():
                op = _FILTER_OPS.get(op_name)
                if op is None:
                    raise ValueError(f"Unsupported filter operator: {op_name}")
                if not op(actual, expected):
                    return False
        else:
            if actual != condition:
                return False
    return True


def _namespace_matches(
    namespace: tuple[str, ...],
    condition: MatchCondition,
) -> bool:
    path = condition.path
    if condition.match_type == "prefix":
        if len(path) > len(namespace):
            return False
        for actual, expected in zip(namespace[: len(path)], path):
            if expected != "*" and actual != expected:
                return False
        return True
    if condition.match_type == "suffix":
        if len(path) > len(namespace):
            return False
        for actual, expected in zip(namespace[-len(path):], path):
            if expected != "*" and actual != expected:
                return False
        return True
    raise ValueError(f"Unknown match_type: {condition.match_type}")


def _starts_with_prefix(namespace: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    if len(prefix) > len(namespace):
        return False
    return namespace[: len(prefix)] == prefix


def _extract_search_text(value: Mapping[str, Any]) -> str:
    """Flatten a value dict into a single string for keyword/embedding scoring."""
    parts: list[str] = []
    for field, sub_value in value.items():
        if isinstance(sub_value, str):
            parts.append(sub_value)
        elif isinstance(sub_value, (int, float, bool)):
            parts.append(str(sub_value))
        else:
            try:
                parts.append(json.dumps(sub_value, default=str))
            except (TypeError, ValueError):
                parts.append(str(sub_value))
    return "\n".join(parts)


class WarmStore(BaseStore):
    """
    LangGraph BaseStore backed by per-namespace WarmMemoryBuffers.

    Each top-level namespace gets its own bounded warm buffer. Writes that exceed
    `capacity` evict the oldest entries within that namespace, so multi-user agents
    naturally get per-user warm memory without cross-tenant eviction.

    Search supports:
    - exact and operator-based filters ($eq, $ne, $gt, $gte, $lt, $lte) over `value`
    - natural-language `query` ranked by a pluggable ImportanceScorer
      (defaults to KeywordImportanceScorer; pass EmbeddingsImportanceScorer for
      semantic search)
    """

    __slots__ = ("capacity", "scorer", "_buffers", "_namespace_lock")

    def __init__(
        self,
        *,
        capacity: int = 32,
        scorer: ImportanceScorer | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.scorer = scorer or KeywordImportanceScorer()
        self._buffers: dict[tuple[str, ...], WarmMemoryBuffer] = {}
        self._namespace_lock = asyncio.Lock()

    def _buffer_for(self, namespace: tuple[str, ...]) -> WarmMemoryBuffer:
        existing = self._buffers.get(namespace)
        if existing is not None:
            return existing
        buffer = WarmMemoryBuffer(capacity=self.capacity, scorer=self.scorer)
        self._buffers[namespace] = buffer
        return buffer

    def _find_row_index(self, buffer: WarmMemoryBuffer, key: str) -> int | None:
        frame = buffer._frame
        if frame.empty:
            return None
        for idx, metadata in enumerate(frame["metadata"].tolist()):
            if isinstance(metadata, dict) and metadata.get("__store_key__") == key:
                return idx
        return None

    def _row_to_item(self, namespace: tuple[str, ...], row: Mapping[str, Any]) -> Item:
        metadata = row["metadata"] if isinstance(row.get("metadata"), dict) else {}
        return Item(
            value=dict(metadata.get("__store_value__") or {}),
            key=str(metadata.get("__store_key__", "")),
            namespace=namespace,
            created_at=metadata.get("__store_created_at__") or datetime.now(timezone.utc),
            updated_at=metadata.get("__store_updated_at__") or datetime.now(timezone.utc),
        )

    def _row_to_search_item(
        self,
        namespace: tuple[str, ...],
        row: Mapping[str, Any],
        score: float | None,
    ) -> SearchItem:
        metadata = row["metadata"] if isinstance(row.get("metadata"), dict) else {}
        return SearchItem(
            namespace=namespace,
            key=str(metadata.get("__store_key__", "")),
            value=dict(metadata.get("__store_value__") or {}),
            created_at=metadata.get("__store_created_at__") or datetime.now(timezone.utc),
            updated_at=metadata.get("__store_updated_at__") or datetime.now(timezone.utc),
            score=score,
        )

    def _do_get(self, op: GetOp) -> Item | None:
        buffer = self._buffers.get(op.namespace)
        if buffer is None:
            return None
        idx = self._find_row_index(buffer, op.key)
        if idx is None:
            return None
        row = buffer._frame.iloc[idx].to_dict()
        return self._row_to_item(op.namespace, row)

    def _do_put(self, op: PutOp) -> None:
        if op.value is None:
            buffer = self._buffers.get(op.namespace)
            if buffer is None:
                return
            idx = self._find_row_index(buffer, op.key)
            if idx is None:
                return
            buffer._frame = buffer._frame.drop(buffer._frame.index[idx]).reset_index(drop=True)
            return

        buffer = self._buffer_for(op.namespace)
        now = datetime.now(timezone.utc)
        existing_idx = self._find_row_index(buffer, op.key)
        created_at = now
        if existing_idx is not None:
            old_metadata = buffer._frame.iloc[existing_idx]["metadata"]
            if isinstance(old_metadata, dict):
                created_at = old_metadata.get("__store_created_at__") or now
            buffer._frame = buffer._frame.drop(buffer._frame.index[existing_idx]).reset_index(drop=True)

        content = _extract_search_text(op.value)
        buffer.add(
            role="item",
            content=content,
            metadata={
                "__store_key__": op.key,
                "__store_value__": dict(op.value),
                "__store_created_at__": created_at,
                "__store_updated_at__": now,
            },
        )

    def _do_search(self, op: SearchOp) -> list[SearchItem]:
        matched_namespaces = [
            ns for ns in self._buffers.keys() if _starts_with_prefix(ns, op.namespace_prefix)
        ]
        candidates: list[tuple[tuple[str, ...], dict[str, Any], float | None]] = []

        for namespace in matched_namespaces:
            buffer = self._buffers[namespace]
            if op.query and op.query.strip():
                ranked = buffer.relevant(op.query, limit=len(buffer))
                for _, row in ranked.iterrows():
                    metadata = row["metadata"] if isinstance(row.get("metadata"), dict) else {}
                    value = dict(metadata.get("__store_value__") or {})
                    if not _matches_filter(value, op.filter):
                        continue
                    candidates.append((namespace, row.to_dict(), float(row.get("score") or 0.0)))
            else:
                for _, row in buffer._frame.iterrows():
                    metadata = row["metadata"] if isinstance(row.get("metadata"), dict) else {}
                    value = dict(metadata.get("__store_value__") or {})
                    if not _matches_filter(value, op.filter):
                        continue
                    candidates.append((namespace, row.to_dict(), None))

        if op.query and op.query.strip():
            candidates.sort(key=lambda triple: (triple[2] or 0.0), reverse=True)
        else:
            def _updated_at(triple: tuple[tuple[str, ...], dict[str, Any], float | None]) -> datetime:
                metadata = triple[1].get("metadata") if isinstance(triple[1].get("metadata"), dict) else {}
                return metadata.get("__store_updated_at__") or datetime.min.replace(tzinfo=timezone.utc)
            candidates.sort(key=_updated_at, reverse=True)

        sliced = candidates[op.offset : op.offset + op.limit]
        return [self._row_to_search_item(ns, row, score) for ns, row, score in sliced]

    def _do_list_namespaces(self, op: ListNamespacesOp) -> list[tuple[str, ...]]:
        namespaces = list(self._buffers.keys())
        if op.match_conditions:
            namespaces = [
                ns for ns in namespaces if all(_namespace_matches(ns, cond) for cond in op.match_conditions)
            ]

        if op.max_depth is not None:
            truncated = {ns[: op.max_depth] for ns in namespaces}
            namespaces = sorted(truncated)
        else:
            namespaces = sorted(set(namespaces))

        return namespaces[op.offset : op.offset + op.limit]

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        ops_list: Sequence[Op] = list(ops)
        results: list[Result] = []
        for op in ops_list:
            if isinstance(op, GetOp):
                results.append(self._do_get(op))
            elif isinstance(op, PutOp):
                self._do_put(op)
                results.append(None)
            elif isinstance(op, SearchOp):
                results.append(self._do_search(op))
            elif isinstance(op, ListNamespacesOp):
                results.append(self._do_list_namespaces(op))
            else:
                raise TypeError(f"Unsupported op type: {type(op).__name__}")
        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        return await asyncio.to_thread(self.batch, list(ops))

    def namespaces(self) -> list[tuple[str, ...]]:
        return sorted(self._buffers.keys())

    def size(self, namespace: tuple[str, ...]) -> int:
        buffer = self._buffers.get(namespace)
        return 0 if buffer is None else len(buffer)
