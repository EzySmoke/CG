import json
import os
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "setup":          os.path.join(DATA_DIR, "setup.json"),
    "medals":         os.path.join(DATA_DIR, "medals.json"),
    "awarded_medals": os.path.join(DATA_DIR, "awarded_medals.json"),
    "strikes":        os.path.join(DATA_DIR, "strikes.json"),
    "aos":            os.path.join(DATA_DIR, "aos.json"),
    "blacklist":      os.path.join(DATA_DIR, "blacklist.json"),
    "loa":            os.path.join(DATA_DIR, "loa.json"),
    "gwarns":         os.path.join(DATA_DIR, "gwarns.json"),
}


def _load(key: str) -> Any:
    path = FILES[key]
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(key: str, data: Any) -> None:
    with open(FILES[key], "w") as f:
        json.dump(data, f, indent=2)


def get_setup() -> dict:           return _load("setup")
def save_setup(data: dict):        _save("setup", data)
def get_medals() -> dict:          return _load("medals")
def save_medals(data: dict):       _save("medals", data)
def get_awarded_medals() -> dict:  return _load("awarded_medals")
def save_awarded_medals(d: dict):  _save("awarded_medals", d)
def get_strikes() -> dict:         return _load("strikes")
def save_strikes(data: dict):      _save("strikes", data)
def get_aos() -> dict:             return _load("aos")
def save_aos(data: dict):          _save("aos", data)
def get_blacklist() -> dict:       return _load("blacklist")
def save_blacklist(data: dict):    _save("blacklist", data)
def get_loa() -> dict:             return _load("loa")
def save_loa(data: dict):          _save("loa", data)
def get_gwarns() -> dict:          return _load("gwarns")
def save_gwarns(data: dict):       _save("gwarns", data)
