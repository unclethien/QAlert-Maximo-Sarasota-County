"""loader-state/manifest.json: what this loader has put on one Maximo instance.

  {"instance": "<MAXIMO_URL>",
   "records": {"<kind>:<our id>": {"kind", "our_id", "maximo_id", "href", "status", "loaded_at", "source"}}}

`source` is "created" or "found" (already on the instance). The file is rewritten after every
record (temp file, then rename), so an interrupted run resumes where it stopped. A manifest
made against another instance is refused rather than trusted.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .config import STATE_DIR


class Manifest:
    def __init__(self, path: Path = STATE_DIR / "manifest.json", instance: str | None = None,
                 persist: bool = True) -> None:
        self.path, self.persist = path, persist
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.instance = data.get("instance") or instance
        if instance and self.instance != instance:
            raise SystemExit(f"{path} was made against {self.instance}, not {instance}. Move it aside to load "
                             "into this instance; the loader will then find its records by natural key.")
        self.entries: dict[str, dict] = data.get("records", {})

    @staticmethod
    def key(kind: str, our_id: str) -> str:
        return f"{kind}:{our_id}"

    def get(self, kind: str, our_id: str) -> dict | None:
        return self.entries.get(self.key(kind, our_id))

    def record(self, kind: str, our_id: str, *, maximo_id: str | None, href: str | None,
               status: str | None = None, source: str = "created") -> dict:
        entry = {"kind": kind, "our_id": our_id, "maximo_id": maximo_id, "href": href, "status": status,
                 "source": source, "loaded_at": datetime.now(UTC).isoformat(timespec="seconds")}
        self.entries[self.key(kind, our_id)] = entry
        self.save()
        return entry

    def set_status(self, kind: str, our_id: str, status: str) -> None:
        self.entries[self.key(kind, our_id)]["status"] = status
        self.save()

    def of_kind(self, kind: str) -> list[dict]:
        return [e for e in self.entries.values() if e["kind"] == kind]

    def save(self) -> None:
        """Write the file. A dry run keeps everything in memory (`persist=False`)."""
        if not self.persist:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        body = {"instance": self.instance, "records": self.entries}
        tmp.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
