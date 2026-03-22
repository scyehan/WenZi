"""Plugin registry — fetch, parse, merge registries and compute plugin status."""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from wenzi.scripting.plugin_meta import (
    INSTALL_TOML,
    PluginMeta,
    find_plugin_dir,
    read_source,
)

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    MANUALLY_PLACED = "manually_placed"
    INCOMPATIBLE = "incompatible"


@dataclass
class PluginInfo:
    meta: PluginMeta
    source_url: str
    registry_name: str
    status: PluginStatus
    installed_version: str | None = None
    is_official: bool = False


class PluginRegistry:
    def __init__(self, plugins_dir: str):
        self._plugins_dir = plugins_dir

    def parse_registry(self, source: str) -> list[dict[str, Any]]:
        _, entries = self.parse_registry_with_name(source)
        return entries

    def parse_registry_with_name(self, source: str) -> tuple[str, list[dict[str, Any]]]:
        raw = read_source(source)
        data = tomllib.loads(raw.decode("utf-8"))
        name = data.get("name", "Unknown")
        entries = data.get("plugins", [])
        return name, [e for e in entries if isinstance(e, dict) and e.get("id")]

    def load_install_info(self, plugin_dir: str) -> dict[str, str] | None:
        install_path = os.path.join(plugin_dir, INSTALL_TOML)
        if not os.path.isfile(install_path):
            return None
        try:
            with open(install_path, "rb") as f:
                data = tomllib.load(f)
            return data.get("install", {})
        except Exception:
            logger.warning("Failed to parse %s", install_path, exc_info=True)
            return None

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in version.split("."))
        except (ValueError, AttributeError):
            return (0,)

    def compute_status(
        self,
        plugin_id: str,
        registry_version: str,
        min_wenzi_version: str,
        current_wenzi_version: str,
    ) -> tuple[PluginStatus, str | None]:
        if min_wenzi_version and current_wenzi_version != "dev":
            if self._parse_version(current_wenzi_version) < self._parse_version(
                min_wenzi_version
            ):
                return PluginStatus.INCOMPATIBLE, None
        local_dir = find_plugin_dir(self._plugins_dir, plugin_id)
        if local_dir is None:
            return PluginStatus.NOT_INSTALLED, None
        install_info = self.load_install_info(local_dir)
        if install_info is None:
            return PluginStatus.MANUALLY_PLACED, None
        installed_ver = install_info.get("installed_version", "")
        if self._parse_version(installed_ver) < self._parse_version(registry_version):
            return PluginStatus.UPDATE_AVAILABLE, installed_ver
        return PluginStatus.INSTALLED, installed_ver

    def _entry_to_plugin_info(
        self,
        entry: dict[str, Any],
        registry_name: str,
        is_official: bool,
        current_wenzi_version: str,
    ) -> PluginInfo | None:
        plugin_id = entry.get("id", "")
        if not plugin_id:
            return None
        source_url = entry.get("source", "")
        meta = PluginMeta(
            name=str(entry.get("name", plugin_id)),
            id=plugin_id,
            description=str(entry.get("description", "")),
            version=str(entry.get("version", "")),
            author=str(entry.get("author", "")),
            min_wenzi_version=str(entry.get("min_wenzi_version", "")),
        )
        status, installed_ver = self.compute_status(
            plugin_id,
            meta.version,
            meta.min_wenzi_version,
            current_wenzi_version,
        )
        return PluginInfo(
            meta=meta,
            source_url=source_url,
            registry_name=registry_name,
            status=status,
            installed_version=installed_ver,
            is_official=is_official,
        )

    def merge_registries(
        self,
        official_source: str,
        extra_sources: list[str],
        current_wenzi_version: str,
    ) -> list[PluginInfo]:
        seen_ids: set[str] = set()
        result: list[PluginInfo] = []

        # Process official registry first — its entries take priority
        try:
            official_name, official_entries = self.parse_registry_with_name(
                official_source
            )
            for entry in official_entries:
                info = self._entry_to_plugin_info(
                    entry, official_name, True, current_wenzi_version
                )
                if info and info.meta.id not in seen_ids:
                    seen_ids.add(info.meta.id)
                    result.append(info)
        except Exception:
            logger.warning(
                "Failed to load official registry %s", official_source, exc_info=True
            )

        # Process extra (third-party) registries — skip duplicates
        for source in extra_sources:
            try:
                reg_name, entries = self.parse_registry_with_name(source)
                for entry in entries:
                    info = self._entry_to_plugin_info(
                        entry, reg_name, False, current_wenzi_version
                    )
                    if info and info.meta.id not in seen_ids:
                        seen_ids.add(info.meta.id)
                        result.append(info)
            except Exception:
                logger.warning(
                    "Failed to load registry %s", source, exc_info=True
                )

        return result
