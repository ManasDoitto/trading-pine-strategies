"""Config and paths for trading_exec. Output goes to exec_data/ (gitignored)."""
import os
import tomllib
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
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
    d = REPO_ROOT / load_config()["paths"]["data_dir"]
    if sub:
        d = d / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def enabled_instruments():
    return [u for u, c in load_config()["instruments"].items() if c.get("enabled")]


def instrument_cfg(underlying):
    return load_config()["instruments"][underlying]


def env(name, default=None):
    """Read a secret from the repo-root .env (same file trading_agents uses)."""
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    return os.getenv(name, default)
