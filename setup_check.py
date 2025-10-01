#!/usr/bin/env python3
"""
Setup verification script for the Space News Video Pipeline
"""

import sys
import subprocess

def check_python_version():
    version = sys.version_info
    print(f"✓ Python {version.major}.{version.minor}.{version.micro} detected")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        return False
    return True

def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ FFmpeg detected: {version_line}")
            return True
    except:
        pass

    print("❌ FFmpeg not found. Install with:")
    print("   Ubuntu/Debian: sudo apt-get install ffmpeg")
    print("   macOS: brew install ffmpeg")
    print("   Windows: Download from https://ffmpeg.org/download.html")
    return False

def check_required_modules():
    required = [
        'requests', 'feedparser', 'gtts', 'tqdm',
        'openai', 'transformers', 'torch', 'whisper'
    ]

    optional = ['supabase', 'psutil', 'dotenv']

    missing = []
    missing_optional = []

    for module in required:
        try:
            __import__(module)
            print(f"✓ {module} installed")
        except ImportError:
            missing.append(module)
            print(f"❌ {module} not installed")

    for module in optional:
        try:
            if module == 'dotenv':
                __import__('dotenv')
            else:
                __import__(module)
            print(f"✓ {module} installed")
        except ImportError:
            missing_optional.append(module)
            print(f"⚠️  {module} not installed (optional for optimization)")

    if missing:
        print("\n❌ Missing required packages. Install with:")
        print("   pip install -r requirements.txt")
        return False

    if missing_optional:
        print("\n⚠️  Missing optional packages (needed for optimized pipeline):")
        print("   pip install supabase python-dotenv psutil")

    return True

def check_config_file():
    import os
    if os.path.exists('pipeline_config.json'):
        print("✓ pipeline_config.json found")
        return True
    else:
        print("❌ pipeline_config.json not found")
        print("   Copy pipeline_config.json.example and add your API keys")
        return False

def main():
    print("=" * 60)
    print("Space News Video Pipeline - Setup Verification")
    print("=" * 60)
    print()

    checks = [
        ("Python Version", check_python_version()),
        ("FFmpeg", check_ffmpeg()),
        ("Python Modules", check_required_modules()),
        ("Configuration", check_config_file())
    ]

    print()
    print("=" * 60)
    print("Summary:")
    print("=" * 60)

    all_passed = all(result for _, result in checks)

    if all_passed:
        print("✅ All checks passed! You're ready to run the pipeline.")
        print("\nRun the pipeline with:")
        print("   python3 space_news_pipeline_optimized.py")
    else:
        print("❌ Some checks failed. Please resolve the issues above.")
        print("\nQuick setup:")
        print("1. Install FFmpeg for your system")
        print("2. Install Python packages: pip install -r requirements.txt")
        print("3. Configure API keys in pipeline_config.json")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
