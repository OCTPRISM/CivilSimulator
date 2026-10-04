"""Lab dataset ingestion — Excel/CSV, Markdown, ZIP + manual events."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class TimelineEvent:
    id: str
    time_label: str
    at_step: int
    title: str
    description: str = ""
    magnitude: float = 0.15
    kind: str = "custom"
    source: str = "manual"
    channel_preview: dict[str, float] = field(default_factory=dict)
    entities: list[str] = field(default_factory=list)
    rationale: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "time_label": self.time_label,
            "at_step": self.at_step,
            "title": self.title,
            "description": self.description,
            "magnitude": self.magnitude,
            "kind": self.kind,
            "source": self.source,
            "channel_preview": self.channel_preview,
            "entities": self.entities,
            "rationale": self.rationale,
        }


_DATE_RE = re.compile(
    r"(?:(\d{4})[年\-/\.](\d{1,2})?[月\-/\.]?(\d{1,2})?[日]?)|"
    r"(?:第(\d+)日)|(?:T\+(\d+))|(?:步数\s*(\d+))"
)


def _parse_step_from_text(text: str, default: int = 0) -> int:
    text = text or ""
    m = _DATE_RE.search(text)
    if not m:
        return default
    if m.group(4):
        return int(m.group(4))
    if m.group(5):
        return int(m.group(5))
    if m.group(6):
        return int(m.group(6))
    if m.group(1):
        year = int(m.group(1))
        return max(0, (year % 100) * 12 + (int(m.group(2) or 1)))
    return default


def parse_csv_text(text: str, source: str = "csv") -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return events
    fields = [f.lower() for f in reader.fieldnames]
    for i, row in enumerate(reader):
        lower = {k.lower(): v for k, v in row.items()}
        title = (lower.get("title") or lower.get("事件") or lower.get("event") or lower.get("name") or "").strip()
        if not title:
            continue
        time_col = lower.get("time") or lower.get("时间") or lower.get("date") or lower.get("日期") or ""
        desc = (lower.get("description") or lower.get("描述") or lower.get("note") or "")[:300]
        mag = float(lower.get("magnitude") or lower.get("冲击") or 0.15)
        step = _parse_step_from_text(str(time_col), default=i * 4)
        events.append(TimelineEvent(
            id=f"ev_{uuid4().hex[:8]}",
            time_label=str(time_col)[:40] or f"T+{step}",
            at_step=step,
            title=title[:120],
            description=desc,
            magnitude=max(-1, min(1, mag)),
            source=source,
        ))
    return events


def parse_markdown_text(text: str, source: str = "markdown") -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    step_acc = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # ## 806年 开仓平粜
        hm = re.match(r"^#{1,3}\s*(.+)$", line)
        if hm:
            title = hm.group(1).strip()
            step = _parse_step_from_text(title, default=step_acc)
            step_acc = step + 4
            events.append(TimelineEvent(
                id=f"ev_{uuid4().hex[:8]}",
                time_label=title[:40],
                at_step=step,
                title=title[:120],
                source=source,
            ))
            continue
        # - 2024-03 政策加码
        bm = re.match(r"^[-*]\s*(.+)$", line)
        if bm:
            raw = bm.group(1).strip()
            parts = re.split(r"[:：]\s*", raw, maxsplit=1)
            title = parts[-1][:120]
            time_label = parts[0][:40] if len(parts) > 1 else raw[:40]
            step = _parse_step_from_text(raw, default=step_acc)
            step_acc = step + 2
            events.append(TimelineEvent(
                id=f"ev_{uuid4().hex[:8]}",
                time_label=time_label,
                at_step=step,
                title=title,
                source=source,
            ))
    return events


def parse_upload(filename: str, content: bytes) -> list[TimelineEvent]:
    name = (filename or "file").lower()
    if name.endswith(".zip"):
        return _parse_zip(content)
    if name.endswith((".csv", ".tsv")):
        text = content.decode("utf-8", errors="replace")
        return parse_csv_text(text, source=name)
    if name.endswith((".md", ".markdown", ".txt")):
        text = content.decode("utf-8", errors="replace")
        return parse_markdown_text(text, source=name)
    if name.endswith((".xlsx", ".xls")):
        return _parse_xlsx(content, name)
    # fallback: try markdown then csv
    text = content.decode("utf-8", errors="replace")
    ev = parse_markdown_text(text, source=name)
    return ev if ev else parse_csv_text(text, source=name)


def _parse_zip(content: bytes) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.filename.startswith("__MACOSX"):
                continue
            try:
                data = zf.read(info)
                events.extend(parse_upload(info.filename, data))
            except Exception:
                continue
    return events


def _parse_xlsx(content: bytes, name: str) -> list[TimelineEvent]:
    try:
        import openpyxl  # type: ignore
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return []
        header = [str(c or "").strip() for c in rows[0]]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        for row in rows[1:]:
            writer.writerow([str(c or "") for c in row])
        return parse_csv_text(buf.getvalue(), source=name)
    except ImportError:
        return [TimelineEvent(
            id=f"ev_{uuid4().hex[:8]}",
            time_label="提示",
            at_step=0,
            title="需安装 openpyxl 以解析 Excel",
            description="请将文件另存为 CSV 后上传，或安装 openpyxl。",
            magnitude=0,
            source=name,
        )]


def parse_manual_events(items: list[dict[str, Any]]) -> list[TimelineEvent]:
    out: list[TimelineEvent] = []
    for i, it in enumerate(items):
        title = (it.get("title") or "").strip()
        if not title:
            continue
        time_label = (it.get("time_label") or it.get("time") or f"T+{i*4}")[:40]
        step = int(it.get("at_step") if it.get("at_step") is not None else _parse_step_from_text(time_label, i * 4))
        out.append(TimelineEvent(
            id=f"ev_{uuid4().hex[:8]}",
            time_label=time_label,
            at_step=step,
            title=title[:120],
            description=(it.get("description") or it.get("note") or "")[:300],
            magnitude=float(it.get("magnitude") or 0.15),
            kind=str(it.get("kind") or "custom"),
            source="manual",
        ))
    return out


def save_upload(user_id: str, lab_id: str, filename: str, content: bytes) -> Path:
    base = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / user_id / lab_id
    base.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.\-]", "_", filename)[:120]
    path = base / f"{uuid4().hex[:8]}_{safe}"
    path.write_bytes(content)
    return path
