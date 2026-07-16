"""Log API backed by the rotating log file.

Both endpoints parse `dealcourier.log` (written by the
``TimedRotatingFileHandler`` configured in ``logging_setup.py``) instead of
querying a database table. This avoids the SQLite read/write lock
contention that previously dropped log rows from the web UI during
long, low-frequency scrape phases (e.g. ricardo's 30s inter-request
delay): the file handler is unaffected by whatever the rest of the
application is doing, so every log record reaches the file.

Line format (must match the formatter in ``logging_setup.py``):

    %(asctime)s | %(levelname)-7s | %(name)s | %(message)s

e.g. ``2026-07-16 20:21:10 | INFO    | dealcourier.scheduler | Scraping ricardo ...``
"""

import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from dealcourier.config import get_config

router = APIRouter(tags=["logs"])

# Cap on how many lines /api/logs reads from the file to keep the
# endpoint cheap even after a long-running process has produced a
# very large current log file.
MAX_HISTORY_LINES = 20000

# Matches the file-handler formatter exactly. The level field is
# padded to 7 chars with spaces, so we strip trailing whitespace.
LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r" \| (?P<level>\w+)\s*"
    r" \| (?P<logger>[^|]+?)"
    r" \| (?P<message>.*)$"
)


def _log_path() -> Path:
    return Path(get_config().log_file)


def _parse_line(line: str) -> dict | None:
    m = LOG_LINE_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    return {
        "timestamp": m.group("timestamp"),
        "level": m.group("level"),
        "logger": m.group("logger").strip(),
        "message": m.group("message"),
    }


def _iter_lines(path: Path):
    """Yield parsed log entries from the file, newest first.

    Reads at most ``MAX_HISTORY_LINES`` lines from the tail of the file
    to bound memory/time for very large current log files.
    """
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as f:
        # Read the tail efficiently: seek to end, then back by a chunk
        # until we have at most MAX_HISTORY_LINES lines.
        f.seek(0, os.SEEK_END)
        size = f.tell()
        chunk = 1 << 16  # 64 KiB
        pos = size
        buf = ""
        lines: list[str] = []
        while pos > 0 and len(lines) <= MAX_HISTORY_LINES:
            read = min(chunk, pos)
            pos -= read
            f.seek(pos)
            data = f.read(read)
            buf = data + buf
            parts = buf.split("\n")
            # First element is a partial line (unless pos == 0); keep it
            # buffered for the next iteration.
            buf = parts[0]
            lines = parts[1:] + lines
        if buf:
            lines = [buf] + lines
        # Trim to the cap (we may have overshot by one chunk).
        lines = lines[-MAX_HISTORY_LINES:]
        for line in reversed(lines):
            if line:
                entry = _parse_line(line)
                if entry:
                    yield entry


@router.get("/logs")
def get_logs(
    level: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """Paginated historical logs, newest first, read from the log file."""
    level_u = level.upper() if level else None
    entries_all = list(_iter_lines(_log_path()))

    filtered = []
    for e in entries_all:
        if level_u and e["level"] != level_u:
            continue
        if search and search not in e["message"] and search not in e["logger"]:
            continue
        filtered.append(e)

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    page_entries = filtered[start:end]

    # Synthesize a monotonically-increasing id for frontend compatibility
    # (the previous DB-backed endpoint returned row ids). Use the index
    # within the filtered set so it is stable within a single response.
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "entries": [
            {
                "id": start + i,
                "timestamp": e["timestamp"],
                "level": e["level"],
                "logger": e["logger"],
                "message": e["message"],
            }
            for i, e in enumerate(page_entries)
        ],
    }


@router.get("/logs/stream")
async def stream_logs():
    """SSE endpoint for live log tailing straight from the log file."""

    async def event_generator():
        path = _log_path()
        f = _open_for_tail(path)
        try:
            # Rotation is detected by comparing the open file's stat
            # to the path's current stat on each loop. In normal
            # operation they're the same file, so the stats track each
            # other exactly. After TimedRotatingFileHandler rotates at
            # midnight, the open file is the renamed (now frozen) file
            # while `path` points at a fresh, growing file, so the two
            # stats will never match again -> we reopen.
            buf = ""

            while True:
                if f is not None:
                    open_id = _stat_id(f)
                else:
                    open_id = None
                try:
                    cur_id = _path_id(path)
                except FileNotFoundError:
                    cur_id = None

                if cur_id != open_id:
                    # Rotation (or the file (re)appeared / disappeared).
                    if f is not None:
                        f.close()
                        f = None
                    if cur_id is None:
                        # File gone; emit keepalive and retry next loop.
                        yield ": keepalive\n\n"
                        await asyncio.sleep(1)
                        continue
                    # The old file was renamed and a fresh (currently
                    # empty) file was created. Seek to its end so we
                    # don't replay any lines already written between
                    # rotation and our detection.
                    f = _open_for_tail(path)
                    buf = ""

                if f is None:
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
                    continue

                chunk = f.read()

                if chunk:
                    buf += chunk
                    # Emit any complete lines; keep the trailing
                    # partial line buffered for the next iteration.
                    if "\n" in buf:
                        parts = buf.split("\n")
                        buf = parts[-1]
                        for line in parts[:-1]:
                            entry = _parse_line(line)
                            if entry is None:
                                continue
                            data = json.dumps(entry)
                            yield f"data: {data}\n\n"
                else:
                    # No new data; keep the connection alive.
                    yield ": keepalive\n\n"

                await asyncio.sleep(1)
        finally:
            if f is not None:
                f.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _open_for_tail(path: Path):
    """Open `path` for tailing, seeked to end. Returns None if missing."""
    if not path.exists():
        return None
    f = path.open("r", encoding="utf-8", errors="replace")
    f.seek(0, os.SEEK_END)
    return f


def _stat_id(f) -> tuple:
    """Return an identity tuple for an open file handle."""
    st = os.fstat(f.fileno())
    # st_ino is unreliable on Windows, so include dev, mtime and size.
    return (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)


def _path_id(path: Path) -> tuple:
    """Return an identity tuple for `path` (must exist)."""
    st = path.stat()
    return (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
