"""CorelDRAW COM integration helpers."""

import shutil
import sys


def reset_generated_com_cache():
    """Remove stale pywin32 generated wrappers before connecting to CorelDRAW."""
    import win32com

    generated_path = getattr(win32com, "__gen_path__", None)
    if generated_path:
        shutil.rmtree(generated_path, ignore_errors=True)
    sys.modules.pop("win32com.gen_py", None)


def connect():
    try:
        import win32com.client
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Corel integration requires the pywin32 package to be installed."
        ) from exc
    reset_generated_com_cache()
    try:
        return win32com.client.dynamic.Dispatch("CorelDRAW.Application")
    except Exception:
        reset_generated_com_cache()
        return win32com.client.dynamic.Dispatch("CorelDRAW.Application")