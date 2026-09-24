"""Compatibility entry point for the shared TunerPro XDF exporter.

Install this editor with ``python -m pip install .`` to resolve the exact
reviewed Universal Exporter commit declared in pyproject.toml.
"""

from pathlib import Path

try:
    import tunerpro_exporter as _exporter
except ModuleNotFoundError as exc:
    if exc.name == "tunerpro_exporter":
        raise ModuleNotFoundError(
            "Install the editor and its pinned shared XDF dependency: "
            "python -m pip install ."
        ) from exc
    raise

UniversalXDFExporter = _exporter.UniversalXDFExporter
__version__ = _exporter.__version__


def __getattr__(name):
    return getattr(_exporter, name)


def ensure_output_parent(output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    raise SystemExit(_exporter.main())
