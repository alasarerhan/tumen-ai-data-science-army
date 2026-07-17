"""Worker memory monitoring service.

Implements memory monitoring with:
* Process memory tracking
* Memory leak detection
* Automatic restart recommendations
* Prometheus metrics

Best Practices Reference:
https://github.com/kpn/arq-prometheus
https://docs.python.org/3/library/resource.html

Usage
-----
::

    from platform_api.services.memory_monitor import MemoryMonitor

    monitor = MemoryMonitor()

    # Check memory usage
    stats = monitor.get_memory_stats()

    # Check for memory leak
    if monitor.detect_memory_leak():
        logger.warning("Memory leak detected!")
"""

from __future__ import annotations

import gc
import importlib.util
import logging
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Dict, List, Optional

from prometheus_client import Gauge

logger = logging.getLogger(__name__)

PROCESS_MEMORY_BYTES = Gauge(
    "platform_api_process_memory_bytes",
    "Current process memory usage in bytes",
    registry=None,
)

PROCESS_MEMORY_RSS = Gauge(
    "platform_api_process_memory_rss_bytes",
    "Process resident set size in bytes",
    registry=None,
)

PROCESS_MEMORY_VMS = Gauge(
    "platform_api_process_memory_vms_bytes",
    "Process virtual memory size in bytes",
    registry=None,
)

PROCESS_MEMORY_PERCENT = Gauge(
    "platform_api_process_memory_percent",
    "Process memory usage as percentage of system memory",
    registry=None,
)

GC_COLLECTIONS = Gauge(
    "platform_api_gc_collections_total",
    "Number of garbage collections",
    ["generation"],
    registry=None,
)

GC_COLLECTED = Gauge(
    "platform_api_gc_collected_total",
    "Total objects collected by GC",
    ["generation"],
    registry=None,
)

MEMORY_GROWTH_RATE = Gauge(
    "platform_api_memory_growth_rate_bytes_per_minute",
    "Memory growth rate in bytes per minute",
    registry=None,
)


@dataclass
class MemorySnapshot:
    """Snapshot of memory usage at a point in time."""
    timestamp: datetime
    rss_bytes: int
    vms_bytes: int
    percent: float
    available_system_memory: int


class MemoryMonitor:
    """Monitor process memory usage and detect leaks.

    Parameters
    ----------
    sample_interval_seconds : int
        Interval between memory samples (default: 60).
    history_size : int
        Number of samples to keep for leak detection (default: 60).
    leak_threshold_percent : float
        Memory growth threshold to consider a leak (default: 10%).
    """

    def __init__(
        self,
        sample_interval_seconds: int = 60,
        history_size: int = 60,
        leak_threshold_percent: float = 10.0,
    ) -> None:
        self._sample_interval = sample_interval_seconds
        self._history_size = history_size
        self._leak_threshold = leak_threshold_percent
        self._history: List[MemorySnapshot] = []
        self._psutil_available = self._check_psutil()

    def _check_psutil(self) -> bool:
        """Check if psutil is available."""
        if importlib.util.find_spec("psutil") is None:
            logger.warning("psutil not available, memory monitoring will be limited")
            return False
        return True

    def get_memory_stats(self) -> Dict:
        """Get current memory statistics.

        Returns
        -------
        dict
            Memory statistics including RSS, VMS, and percentage.
        """
        if self._psutil_available:
            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            system_memory = psutil.virtual_memory()

            stats = {
                "rss_bytes": memory_info.rss,
                "vms_bytes": memory_info.vms,
                "percent": memory_percent,
                "available_system_memory": system_memory.available,
                "total_system_memory": system_memory.total,
                "process_count": len(psutil.pids()),
            }

            PROCESS_MEMORY_BYTES.set(memory_info.rss)
            PROCESS_MEMORY_RSS.set(memory_info.rss)
            PROCESS_MEMORY_VMS.set(memory_info.vms)
            PROCESS_MEMORY_PERCENT.set(memory_percent)

            snapshot = MemorySnapshot(
                timestamp=datetime.now(UTC),
                rss_bytes=memory_info.rss,
                vms_bytes=memory_info.vms,
                percent=memory_percent,
                available_system_memory=system_memory.available,
            )
            self._add_snapshot(snapshot)

            return stats

        else:
            import tracemalloc

            if not tracemalloc.is_tracing():
                tracemalloc.start()

            current, peak = tracemalloc.get_traced_memory()

            stats = {
                "rss_bytes": current,
                "vms_bytes": peak,
                "percent": 0.0,
                "available_system_memory": 0,
                "total_system_memory": 0,
                "process_count": 1,
            }

            PROCESS_MEMORY_BYTES.set(current)
            PROCESS_MEMORY_RSS.set(current)
            PROCESS_MEMORY_VMS.set(peak)

            return stats

    def _add_snapshot(self, snapshot: MemorySnapshot) -> None:
        """Add a memory snapshot to history."""
        self._history.append(snapshot)
        if len(self._history) > self._history_size:
            self._history.pop(0)

    def detect_memory_leak(self) -> bool:
        """Detect if there's a memory leak.

        Compares memory usage over time to detect consistent growth.

        Returns
        -------
        bool
            True if a memory leak is detected.
        """
        if len(self._history) < 10:
            return False

        first_half = self._history[:len(self._history)//2]
        second_half = self._history[len(self._history)//2:]

        first_avg = sum(s.rss_bytes for s in first_half) / len(first_half)
        second_avg = sum(s.rss_bytes for s in second_half) / len(second_half)

        if first_avg == 0:
            return False

        growth_percent = ((second_avg - first_avg) / first_avg) * 100

        if growth_percent > self._leak_threshold:
            logger.warning(
                "Memory leak detected: growth=%.1f%% over %d samples",
                growth_percent, len(self._history),
            )
            return True

        return False

    def get_memory_growth_rate(self) -> float:
        """Calculate memory growth rate in bytes per minute.

        Returns
        -------
        float
            Memory growth rate in bytes per minute.
        """
        if len(self._history) < 2:
            return 0.0

        first = self._history[0]
        last = self._history[-1]

        time_diff = (last.timestamp - first.timestamp).total_seconds()
        if time_diff == 0:
            return 0.0

        memory_diff = last.rss_bytes - first.rss_bytes
        growth_rate = (memory_diff / time_diff) * 60

        MEMORY_GROWTH_RATE.set(growth_rate)

        return growth_rate

    def get_gc_stats(self) -> Dict:
        """Get garbage collection statistics.

        Returns
        -------
        dict
            GC statistics.
        """
        gc_stats = {
            "collections": {},
            "threshold": gc.get_threshold(),
            "count": gc.get_count(),
            "enabled": gc.isenabled(),
        }

        for i, count in enumerate(gc.get_count()):
            GC_COLLECTIONS.labels(generation=str(i)).set(count)

        return gc_stats

    def force_gc(self) -> Dict:
        """Force garbage collection and return stats.

        Returns
        -------
        dict
            Collection statistics.
        """
        before = self.get_memory_stats()

        collected = gc.collect()

        after = self.get_memory_stats()

        for i, c in enumerate(collected):
            GC_COLLECTED.labels(generation=str(i)).set(c)

        return {
            "collected": collected,
            "before_rss": before["rss_bytes"],
            "after_rss": after["rss_bytes"],
            "freed_bytes": before["rss_bytes"] - after["rss_bytes"],
        }

    def get_recommendations(self) -> List[str]:
        """Get memory optimization recommendations.

        Returns
        -------
        list[str]
            List of recommendations.
        """
        recommendations = []
        stats = self.get_memory_stats()

        if stats["percent"] > 80:
            recommendations.append(
                "Memory usage is above 80%. Consider increasing system memory "
                "or optimizing memory-intensive operations."
            )

        if self.detect_memory_leak():
            recommendations.append(
                "Memory leak detected. Review long-running processes and "
                "check for unclosed resources (connections, files, etc.)."
            )

        growth_rate = self.get_memory_growth_rate()
        if growth_rate > 10 * 1024 * 1024:  # 10 MB/min
            recommendations.append(
                f"High memory growth rate ({growth_rate / 1024 / 1024:.1f} MB/min). "
                "Consider implementing memory limits or periodic restarts."
            )

        if not gc.isenabled():
            recommendations.append(
                "Garbage collection is disabled. Consider enabling it for "
                "automatic memory management."
            )

        if not recommendations:
            recommendations.append("Memory usage looks healthy.")

        return recommendations

    def should_restart(self, memory_limit_mb: int = 1024) -> bool:
        """Check if the process should be restarted due to memory usage.

        Parameters
        ----------
        memory_limit_mb : int
            Memory limit in MB before recommending restart.

        Returns
        -------
        bool
            True if restart is recommended.
        """
        stats = self.get_memory_stats()
        current_mb = stats["rss_bytes"] / (1024 * 1024)

        if current_mb > memory_limit_mb:
            logger.warning(
                "Memory limit exceeded: current=%.1f MB, limit=%d MB",
                current_mb, memory_limit_mb,
            )
            return True

        if self.detect_memory_leak():
            return True

        return False


_memory_monitor: Optional[MemoryMonitor] = None
_memory_monitor_lock = threading.Lock()


def get_memory_monitor() -> MemoryMonitor:
    """Get a singleton memory monitor instance.

    Returns
    -------
    MemoryMonitor
        Memory monitor instance.
    """
    global _memory_monitor
    if _memory_monitor is None:
        with _memory_monitor_lock:
            if _memory_monitor is None:
                _memory_monitor = MemoryMonitor()
    return _memory_monitor


__all__ = [
    "MemoryMonitor",
    "MemorySnapshot",
    "get_memory_monitor",
    "PROCESS_MEMORY_BYTES",
    "PROCESS_MEMORY_RSS",
    "PROCESS_MEMORY_VMS",
    "PROCESS_MEMORY_PERCENT",
    "MEMORY_GROWTH_RATE",
]
