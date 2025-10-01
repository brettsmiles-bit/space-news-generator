import os
import psutil
import threading
from typing import Optional

class ResourceManager:
    def __init__(self):
        self.cpu_count = os.cpu_count() or 4
        self.memory_total = psutil.virtual_memory().total
        self.disk_path = "/"

    def get_optimal_workers(self, min_workers: int = 2, max_workers: int = 8) -> int:
        available_memory = psutil.virtual_memory().available
        memory_gb = available_memory / (1024 ** 3)

        if memory_gb < 4:
            workers = min_workers
        elif memory_gb < 8:
            workers = min(self.cpu_count // 2, max_workers)
        else:
            workers = min(self.cpu_count, max_workers)

        return max(min_workers, workers)

    def check_disk_space(self, required_gb: float = 5.0) -> bool:
        disk = psutil.disk_usage(self.disk_path)
        available_gb = disk.free / (1024 ** 3)

        return available_gb >= required_gb

    def get_memory_usage_percent(self) -> float:
        return psutil.virtual_memory().percent

    def is_memory_constrained(self, threshold: float = 85.0) -> bool:
        return self.get_memory_usage_percent() > threshold

    def get_cpu_usage_percent(self) -> float:
        return psutil.cpu_percent(interval=1)

    def should_throttle(self, cpu_threshold: float = 90.0,
                       memory_threshold: float = 85.0) -> bool:
        return (self.get_cpu_usage_percent() > cpu_threshold or
                self.is_memory_constrained(memory_threshold))

    def wait_for_resources(self, timeout: int = 300):
        start_time = threading.Event()
        elapsed = 0

        while self.should_throttle() and elapsed < timeout:
            start_time.wait(5)
            elapsed += 5

    def get_system_info(self) -> dict:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.disk_path)

        return {
            "cpu_count": self.cpu_count,
            "cpu_usage": self.get_cpu_usage_percent(),
            "memory_total_gb": memory.total / (1024 ** 3),
            "memory_available_gb": memory.available / (1024 ** 3),
            "memory_percent": memory.percent,
            "disk_total_gb": disk.total / (1024 ** 3),
            "disk_free_gb": disk.free / (1024 ** 3),
            "disk_percent": disk.percent
        }
