"""Source auto-discovery: finds and instantiates Source subclasses at startup.

Replaces the hand-maintained `_SOURCES` dict in main.py. `config.yaml`'s
`sources:` section remains the single registry of record — discovery scans the
`sources/` package for concrete `Source` subclasses, but a source is only
instantiated when its `name` appears in the config with `enabled: true`.
A disabled or unconfigured source is never instantiated (which also keeps the
fragile LinkedIn source cold unless explicitly enabled).

Rules:
- a class is discoverable if it subclasses Source, is concrete, is defined in
  the scanned module (not merely imported into it), and has a non-default name
- a module that fails to import is logged and skipped — one broken source
  file can't take down startup (consistent with source failure isolation)
- duplicate names are logged and the first discovery wins
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any, Iterator

from sources.base import Source

logger = logging.getLogger(__name__)


def iter_source_classes(package_name: str = "sources") -> Iterator[type[Source]]:
    """Yield concrete Source subclasses defined in `package_name`'s modules."""
    package = importlib.import_module(package_name)
    for mod_info in pkgutil.iter_modules(package.__path__):
        qualname = f"{package_name}.{mod_info.name}"
        try:
            module = importlib.import_module(qualname)
        except Exception:
            logger.warning("Discovery: failed to import %s — skipping", qualname, exc_info=True)
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, Source)
                and cls is not Source
                and not inspect.isabstract(cls)
                and cls.__module__ == module.__name__
            ):
                yield cls


def discover_sources(
    sources_config: dict[str, Any],
    package_name: str = "sources",
) -> dict[str, Source]:
    """Return {name: instance} for every discovered source enabled in config.

    Opt-in per source: a class whose `name` is missing from `sources_config`
    or not `enabled: true` is skipped *before* instantiation.
    """
    registry: dict[str, Source] = {}
    for cls in iter_source_classes(package_name):
        name = getattr(cls, "name", None)
        if not name or name == Source.name:
            logger.warning("Discovery: %s has no usable `name` — skipping", cls.__qualname__)
            continue
        if name in registry:
            logger.warning(
                "Discovery: duplicate source name %r (%s) — keeping %s",
                name, cls.__qualname__, type(registry[name]).__qualname__,
            )
            continue
        if not sources_config.get(name, {}).get("enabled", False):
            logger.debug("Discovery: source %r disabled or unconfigured — not instantiated", name)
            continue
        registry[name] = cls()

    logger.info("Discovery: %d enabled source(s): %s", len(registry), sorted(registry) or "(none)")
    return registry
