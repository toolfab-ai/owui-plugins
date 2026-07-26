import importlib.util
from pathlib import Path


def _find_plugin_dir(plugins_dir: Path, plugin_name: str) -> Path:
    """Find plugin directory, trying both ``<name>`` and ``<name>.local``."""
    candidates = [
        plugins_dir / plugin_name,
        plugins_dir / f"{plugin_name}.local",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Plugin directory '{plugin_name}' not found in {plugins_dir}")


def load_plugin(plugin_name: str):
    """Load a plugin module by name from the plugins directory.

    Supports both flat ``<name>.py`` and built ``plugin.py`` layouts,
    as well as ``<name>.local/`` directories (local-only plugins).
    """
    plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
    plugin_dir = _find_plugin_dir(plugins_dir, plugin_name)
    candidates = [
        plugin_dir / f"{plugin_name}.py",
        plugin_dir / f"{plugin_name.split('-')[0]}.py",
        plugin_dir / "plugin.py",
        plugin_dir / "src" / "main.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            mod_name = plugin_name.replace("-", "_")
            spec = importlib.util.spec_from_file_location(mod_name, candidate)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError(
        f"Plugin source not found in {plugin_dir}. Tried: {', '.join(str(c) for c in candidates)}"
    )
