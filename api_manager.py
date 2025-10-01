import time
import requests
from typing import Optional, Callable, Dict, Any
from functools import wraps
from database_client import DatabaseClient

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = {}
        self.last_failure_time = {}

    def is_open(self, source: str) -> bool:
        if source not in self.failures:
            return False

        if self.failures[source] >= self.failure_threshold:
            elapsed = time.time() - self.last_failure_time.get(source, 0)
            if elapsed < self.timeout:
                return True
            else:
                self.failures[source] = 0

        return False

    def record_success(self, source: str):
        self.failures[source] = 0

    def record_failure(self, source: str):
        self.failures[source] = self.failures.get(source, 0) + 1
        self.last_failure_time[source] = time.time()

class APIManager:
    def __init__(self, db_client: DatabaseClient):
        self.db = db_client
        self.circuit_breaker = CircuitBreaker()
        self.api_keys = {}

    def set_api_keys(self, pexels_key: str, pixabay_key: str,
                    unsplash_key: str, giphy_key: str):
        self.api_keys = {
            "pexels": pexels_key,
            "pixabay": pixabay_key,
            "unsplash": unsplash_key,
            "giphy": giphy_key
        }

    def retry_with_backoff(self, func: Callable, max_retries: int = 3,
                          base_delay: float = 1.0, source: str = "unknown") -> Any:
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result = func()
                response_time = int((time.time() - start_time) * 1000)

                self.db.track_api_call(source, "", True, response_time)
                self.circuit_breaker.record_success(source)

                return result

            except Exception as e:
                response_time = int((time.time() - start_time) * 1000)
                self.db.track_api_call(source, "", False, response_time, str(e))
                self.circuit_breaker.record_failure(source)

                if attempt == max_retries - 1:
                    raise

                delay = base_delay * (2 ** attempt)
                time.sleep(delay)

        return None

    def search_with_fallback(self, query: str, prefer_video: bool = False) -> Optional[str]:
        cached = self.db.get_cached_media(query)
        if cached:
            return cached["media_url"]

        search_order = ["nasa", "pixabay", "pexels", "unsplash"]
        if prefer_video:
            search_order = ["pixabay", "nasa", "pexels", "giphy"]

        for source in search_order:
            if self.circuit_breaker.is_open(source):
                continue

            health = self.db.get_api_health(source, minutes=30)
            if health["success_rate"] < 0.3:
                continue

            try:
                url = self._search_source(source, query)
                if url:
                    return url
            except:
                continue

        return None

    def _search_source(self, source: str, query: str) -> Optional[str]:
        if source == "nasa":
            return self.retry_with_backoff(
                lambda: self._search_nasa(query),
                source="nasa"
            )
        elif source == "pexels":
            return self.retry_with_backoff(
                lambda: self._search_pexels(query),
                source="pexels"
            )
        elif source == "pixabay":
            return self.retry_with_backoff(
                lambda: self._search_pixabay(query),
                source="pixabay"
            )
        elif source == "unsplash":
            return self.retry_with_backoff(
                lambda: self._search_unsplash(query),
                source="unsplash"
            )
        elif source == "giphy":
            return self.retry_with_backoff(
                lambda: self._search_giphy(query),
                source="giphy"
            )
        return None

    def _search_nasa(self, query: str) -> Optional[str]:
        url = f"https://images-api.nasa.gov/search?q={query}&media_type=image,video"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            items = r.json()["collection"]["items"]
            if items:
                links = items[0].get("links", [])
                if links:
                    return links[0]["href"]
        return None

    def _search_pexels(self, query: str) -> Optional[str]:
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
        headers = {"Authorization": self.api_keys.get("pexels", "")}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and r.json()["photos"]:
            return r.json()["photos"][0]["src"]["large"]
        return None

    def _search_pixabay(self, query: str) -> Optional[str]:
        url = f"https://pixabay.com/api/?key={self.api_keys.get('pixabay', '')}&q={query}&image_type=photo&video_type=all"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.json()["hits"]:
            hit = r.json()["hits"][0]
            return hit.get("largeImageURL") or hit.get("videos", {}).get("medium", {}).get("url")
        return None

    def _search_unsplash(self, query: str) -> Optional[str]:
        url = f"https://api.unsplash.com/search/photos?query={query}&client_id={self.api_keys.get('unsplash', '')}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.json()["results"]:
            return r.json()["results"][0]["urls"]["regular"]
        return None

    def _search_giphy(self, query: str) -> Optional[str]:
        url = f"https://api.giphy.com/v1/gifs/search?q={query}&api_key={self.api_keys.get('giphy', '')}&limit=1"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.json()["data"]:
            return r.json()["data"][0]["images"]["original"]["url"]
        return None
