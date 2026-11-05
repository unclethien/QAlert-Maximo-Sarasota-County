"""Connection settings, read from the environment or the repo's gitignored .env file."""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "loader-state"
DATA_DIR = ROOT / "data"

sys.path.insert(0, str(ROOT / "scripts"))
import pilot_catalog as cat  # noqa: E402  (catalog lives next to the generator)

ORGID, SITEID = cat.ORGID, cat.SITEID


@dataclass(frozen=True)
class Settings:
    url: str
    api_key: str = field(repr=False)
    api_path: str = "api"
    itemsetid: str = ""
    verify_tls: bool = True

    def __repr__(self) -> str:  # never show the key, even in tracebacks
        return f"Settings(url={self.url!r}, api_path={self.api_path!r}, itemsetid={self.itemsetid!r}, verify_tls={self.verify_tls})"


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Read settings. Exits with the names (never the values) of anything missing."""
    if env is None:
        try:
            from dotenv import load_dotenv
        except ImportError:
            sys.exit("Missing dependencies. Run: pip install -r requirements.txt")
        load_dotenv(ROOT / ".env", override=False)
        env = dict(os.environ)
    missing = [name for name in ("MAXIMO_URL", "MAXIMO_API_KEY") if not env.get(name)]
    if missing:
        sys.exit(f"Set {' and '.join(missing)} in .env (see .env.example).")
    return Settings(
        url=env["MAXIMO_URL"].rstrip("/"),
        api_key=env["MAXIMO_API_KEY"],
        api_path=(env.get("MAXIMO_API_PATH") or "api").strip("/"),
        itemsetid=env.get("MAXIMO_ITEMSETID", ""),
        verify_tls=env.get("MAXIMO_VERIFY_TLS", "true").strip().lower() not in ("false", "0", "no"),
    )
