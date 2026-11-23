"""Import a pipeline script as a module (its file name starts with a digit)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_script(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
