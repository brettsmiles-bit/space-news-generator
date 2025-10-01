import subprocess
import platform
from typing import Dict, Optional

class GPUDetector:
    def __init__(self):
        self.gpu_info = self.detect_gpu()

    def detect_gpu(self) -> Dict[str, any]:
        system = platform.system()

        if system == "Linux":
            return self._detect_linux_gpu()
        elif system == "Darwin":
            return self._detect_macos_gpu()
        elif system == "Windows":
            return self._detect_windows_gpu()

        return {"available": False, "type": "cpu"}

    def _detect_linux_gpu(self) -> Dict:
        try:
            nvidia_check = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if nvidia_check.returncode == 0 and nvidia_check.stdout.strip():
                return {
                    "available": True,
                    "type": "nvidia",
                    "name": nvidia_check.stdout.strip(),
                    "encoder": "h264_nvenc",
                    "decoder": "h264_cuvid",
                    "scale_filter": "scale_cuda"
                }
        except:
            pass

        try:
            vaapi_check = subprocess.run(
                ["vainfo"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if vaapi_check.returncode == 0 and "VAProfile" in vaapi_check.stdout:
                return {
                    "available": True,
                    "type": "vaapi",
                    "encoder": "h264_vaapi",
                    "scale_filter": "scale_vaapi"
                }
        except:
            pass

        return {"available": False, "type": "cpu"}

    def _detect_macos_gpu(self) -> Dict:
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout:
                return {
                    "available": True,
                    "type": "videotoolbox",
                    "encoder": "h264_videotoolbox",
                    "scale_filter": "scale"
                }
        except:
            pass

        return {"available": False, "type": "cpu"}

    def _detect_windows_gpu(self) -> Dict:
        try:
            nvidia_check = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=True
            )

            if nvidia_check.returncode == 0 and nvidia_check.stdout.strip():
                return {
                    "available": True,
                    "type": "nvidia",
                    "name": nvidia_check.stdout.strip(),
                    "encoder": "h264_nvenc",
                    "decoder": "h264_cuvid",
                    "scale_filter": "scale_cuda"
                }
        except:
            pass

        return {"available": False, "type": "cpu"}

    def get_ffmpeg_encoding_args(self, resolution: str, crf: str = "23",
                                 preset: str = "fast") -> list:
        if not self.gpu_info["available"]:
            return [
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", crf
            ]

        gpu_type = self.gpu_info["type"]

        if gpu_type == "nvidia":
            return [
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-rc", "vbr",
                "-cq", crf,
                "-b:v", "0"
            ]
        elif gpu_type == "videotoolbox":
            return [
                "-c:v", "h264_videotoolbox",
                "-b:v", "5M"
            ]
        elif gpu_type == "vaapi":
            return [
                "-c:v", "h264_vaapi",
                "-qp", crf
            ]

        return [
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", crf
        ]

    def get_scale_filter(self, resolution: str) -> str:
        if not self.gpu_info["available"]:
            return f"scale={resolution}"

        gpu_type = self.gpu_info["type"]

        if gpu_type == "nvidia":
            return f"scale_cuda={resolution}"
        elif gpu_type == "vaapi":
            return f"scale_vaapi=w={resolution.split('x')[0]}:h={resolution.split('x')[1]}"
        else:
            return f"scale={resolution}"

    def requires_hw_upload(self) -> bool:
        return self.gpu_info.get("type") in ["nvidia", "vaapi"]

    def get_hw_upload_filter(self) -> Optional[str]:
        gpu_type = self.gpu_info.get("type")

        if gpu_type == "nvidia":
            return "hwupload_cuda"
        elif gpu_type == "vaapi":
            return "format=nv12,hwupload"

        return None
