"""Execute a sibling ``__pycache__/*.cpython-312.pyc`` into the caller's module namespace."""

from __future__ import annotations

import marshal
import os
import sys


def exec_sibling_pyc(pyc_basename: str) -> None:
    caller = sys._getframe(1)
    shim_file = caller.f_globals.get("__file__")
    if not shim_file:
        raise RuntimeError("exec_sibling_pyc: caller module has no __file__")
    pkg_dir = os.path.dirname(os.path.abspath(shim_file))
    pyc_path = os.path.join(pkg_dir, "__pycache__", pyc_basename)
    if not os.path.isfile(pyc_path):
        raise FileNotFoundError(pyc_path)
    mod = sys.modules[caller.f_globals["__name__"]]
    with open(pyc_path, "rb") as f:
        f.read(16)
        code = marshal.load(f)
    exec(code, mod.__dict__)
