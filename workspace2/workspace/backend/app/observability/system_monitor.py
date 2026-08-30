"""Cross-platform, local-only system overview for the dashboard."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any


class SystemMonitor:
    def snapshot(self, data_dir: Path) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count() or 0,
            "storage": self._storage(data_dir),
        }
        try:
            import psutil  # type: ignore

            memory = psutil.virtual_memory()
            payload.update(
                {
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "memory": {"total": memory.total, "used": memory.used, "percent": memory.percent},
                    "network": {"is_local_only": True},
                }
            )
        except ImportError:
            payload["metrics_detail"] = "Install optional psutil for live CPU and RAM utilisation."
        return payload

    @staticmethod
    def _storage(data_dir: Path) -> dict[str, int | float]:
        usage = shutil.disk_usage(data_dir)
        return {"total": usage.total, "used": usage.used, "free": usage.free, "percent": round((usage.used / usage.total) * 100, 1)}
