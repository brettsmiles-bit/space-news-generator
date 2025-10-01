from typing import Dict, Any

class ConfigPresets:
    PRESETS = {
        "ultra_fast": {
            "resolution": "640x360",
            "preset": "ultrafast",
            "crf": "30",
            "use_ken_burns": False,
            "max_workers": 8,
            "articles_per_feed": 1,
            "transition_type": "fade",
            "transition_duration": 0.3,
            "enable_transcription_cache": True,
            "enable_media_cache": True,
            "enable_script_cache": True,
            "prefer_cached": True,
            "skip_quality_check": True
        },

        "fast": {
            "resolution": "854x480",
            "preset": "veryfast",
            "crf": "28",
            "use_ken_burns": False,
            "max_workers": 6,
            "articles_per_feed": 2,
            "transition_type": "fade",
            "transition_duration": 0.5,
            "enable_transcription_cache": True,
            "enable_media_cache": True,
            "enable_script_cache": True,
            "prefer_cached": True,
            "skip_quality_check": False
        },

        "balanced": {
            "resolution": "1280x720",
            "preset": "medium",
            "crf": "23",
            "use_ken_burns": True,
            "max_workers": 4,
            "articles_per_feed": 3,
            "transition_type": "fade",
            "transition_duration": 0.8,
            "enable_transcription_cache": True,
            "enable_media_cache": True,
            "enable_script_cache": True,
            "prefer_cached": False,
            "skip_quality_check": False
        },

        "hq": {
            "resolution": "1920x1080",
            "preset": "slow",
            "crf": "20",
            "use_ken_burns": True,
            "max_workers": 3,
            "articles_per_feed": 5,
            "transition_type": "fadeblack",
            "transition_duration": 1.0,
            "enable_transcription_cache": True,
            "enable_media_cache": True,
            "enable_script_cache": True,
            "prefer_cached": False,
            "skip_quality_check": False
        },

        "production": {
            "resolution": "1920x1080",
            "preset": "slower",
            "crf": "18",
            "use_ken_burns": True,
            "max_workers": 2,
            "articles_per_feed": 5,
            "transition_type": "circleopen",
            "transition_duration": 1.2,
            "enable_transcription_cache": True,
            "enable_media_cache": True,
            "enable_script_cache": True,
            "prefer_cached": False,
            "skip_quality_check": False
        }
    }

    @classmethod
    def get_preset(cls, name: str) -> Dict[str, Any]:
        if name not in cls.PRESETS:
            raise ValueError(f"Unknown preset: {name}. Available: {list(cls.PRESETS.keys())}")

        return cls.PRESETS[name].copy()

    @classmethod
    def merge_with_preset(cls, preset_name: str, custom_config: Dict[str, Any]) -> Dict[str, Any]:
        preset = cls.get_preset(preset_name)
        preset.update(custom_config)
        return preset

    @classmethod
    def list_presets(cls) -> list:
        return list(cls.PRESETS.keys())

    @classmethod
    def get_preset_description(cls, name: str) -> str:
        descriptions = {
            "ultra_fast": "Lowest quality, fastest render. Good for testing pipeline. 360p, no effects.",
            "fast": "Low quality, fast render. Quick previews. 480p, basic transitions.",
            "balanced": "Good quality-speed balance. Recommended for most use cases. 720p, Ken Burns.",
            "hq": "High quality, slower render. Great for final videos. 1080p, smooth effects.",
            "production": "Highest quality, slowest render. Professional output. 1080p, best settings."
        }
        return descriptions.get(name, "No description available")
