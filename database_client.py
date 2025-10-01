import os
import hashlib
import json
from datetime import datetime, timedelta
from supabase import create_client, Client
from typing import Optional, Dict, List, Any

class DatabaseClient:
    def __init__(self):
        supabase_url = os.getenv("VITE_SUPABASE_URL")
        supabase_key = os.getenv("VITE_SUPABASE_SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found in environment variables")

        self.client: Client = create_client(supabase_url, supabase_key)

    def get_cached_media(self, query: str, source: Optional[str] = None) -> Optional[Dict]:
        normalized_query = self._normalize_query(query)

        query_builder = self.client.table("media_cache").select("*").eq("query", normalized_query).gt("expires_at", datetime.now().isoformat())

        if source:
            query_builder = query_builder.eq("source", source)

        result = query_builder.order("quality_score", desc=True).order("use_count", desc=True).limit(1).execute()

        if result.data:
            media = result.data[0]
            self.client.table("media_cache").update({
                "last_used_at": datetime.now().isoformat(),
                "use_count": media["use_count"] + 1
            }).eq("id", media["id"]).execute()

            return media

        return None

    def save_media_cache(self, query: str, source: str, media_url: str,
                        local_path: str, file_hash: str, media_type: str,
                        resolution: Optional[str] = None, file_size: int = 0,
                        quality_score: int = 5) -> Dict:
        normalized_query = self._normalize_query(query)

        existing = self.client.table("media_cache").select("id").eq("file_hash", file_hash).execute()

        if existing.data:
            return existing.data[0]

        data = {
            "query": normalized_query,
            "source": source,
            "media_url": media_url,
            "local_path": local_path,
            "file_hash": file_hash,
            "media_type": media_type,
            "resolution": resolution,
            "file_size": file_size,
            "quality_score": quality_score,
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat()
        }

        result = self.client.table("media_cache").insert(data).execute()
        return result.data[0]

    def track_api_call(self, source: str, query: str, success: bool,
                      response_time_ms: int, error_message: Optional[str] = None):
        data = {
            "source": source,
            "query": query,
            "success": success,
            "response_time_ms": response_time_ms,
            "error_message": error_message
        }

        self.client.table("api_tracking").insert(data).execute()

    def get_api_health(self, source: str, minutes: int = 60) -> Dict[str, Any]:
        cutoff_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()

        result = self.client.table("api_tracking").select("success, response_time_ms").eq("source", source).gt("created_at", cutoff_time).execute()

        if not result.data:
            return {"success_rate": 1.0, "avg_response_time": 0, "total_calls": 0}

        total_calls = len(result.data)
        successful_calls = sum(1 for call in result.data if call["success"])
        avg_response_time = sum(call["response_time_ms"] for call in result.data) / total_calls

        return {
            "success_rate": successful_calls / total_calls,
            "avg_response_time": avg_response_time,
            "total_calls": total_calls
        }

    def create_render_job(self, job_name: str, mode: str = "balanced") -> Dict:
        data = {
            "job_name": job_name,
            "mode": mode,
            "status": "pending",
            "started_at": datetime.now().isoformat()
        }

        result = self.client.table("render_jobs").insert(data).execute()
        return result.data[0]

    def update_render_job(self, job_id: str, updates: Dict):
        updates["updated_at"] = datetime.now().isoformat()
        self.client.table("render_jobs").update(updates).eq("id", job_id).execute()

    def get_cached_transcription(self, audio_hash: str, model: str) -> Optional[List[Dict]]:
        result = self.client.table("transcription_cache").select("segments").eq("audio_hash", audio_hash).eq("model", model).execute()

        if result.data:
            self.client.table("transcription_cache").update({
                "last_used_at": datetime.now().isoformat()
            }).eq("audio_hash", audio_hash).execute()

            return result.data[0]["segments"]

        return None

    def save_transcription_cache(self, audio_hash: str, model: str,
                                segments: List[Dict], duration_sec: int):
        data = {
            "audio_hash": audio_hash,
            "model": model,
            "segments": json.dumps(segments),
            "duration_sec": duration_sec
        }

        self.client.table("transcription_cache").upsert(data).execute()

    def get_cached_script(self, articles_hash: str) -> Optional[str]:
        result = self.client.table("script_cache").select("script_text").eq("articles_hash", articles_hash).execute()

        if result.data:
            self.client.table("script_cache").update({
                "last_used_at": datetime.now().isoformat()
            }).eq("articles_hash", articles_hash).execute()

            return result.data[0]["script_text"]

        return None

    def save_script_cache(self, articles_hash: str, script_text: str,
                         model: str, word_count: int):
        data = {
            "articles_hash": articles_hash,
            "script_text": script_text,
            "model": model,
            "word_count": word_count
        }

        self.client.table("script_cache").upsert(data).execute()

    def cleanup_expired_cache(self):
        now = datetime.now().isoformat()
        self.client.table("media_cache").delete().lt("expires_at", now).execute()

    def _normalize_query(self, query: str) -> str:
        return " ".join(query.lower().split())

    @staticmethod
    def hash_content(content: Any) -> str:
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        elif isinstance(content, bytes):
            content_bytes = content
        else:
            content_bytes = str(content).encode('utf-8')

        return hashlib.sha256(content_bytes).hexdigest()

    @staticmethod
    def hash_file(file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
