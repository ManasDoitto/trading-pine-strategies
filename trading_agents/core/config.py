"""Config + filesystem locations. All agent output lives under journal_data/ (gitignored)."""
import tomllib
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_DIR.parent
CONFIG_PATH = PKG_DIR / "config.toml"

_config = None


def load_config(path=None):
    global _config
    if path is not None:
        with open(path, "rb") as f:
            return tomllib.load(f)
    if _config is None:
        with open(CONFIG_PATH, "rb") as f:
            _config = tomllib.load(f)
    return _config


def data_dir(sub=None):
    cfg = load_config()
    root = REPO_ROOT / cfg["paths"]["data_dir"]
    d = root / sub if sub else root
    d.mkdir(parents=True, exist_ok=True)
    return d


def in_scope(underlying):
    return underlying in load_config()["instruments"]
