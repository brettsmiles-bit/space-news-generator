# Setup Instructions

## Current Issue

Your Python environment is missing pip (the package installer) and the required dependencies.

## Solution

### Option 1: Install pip (Recommended)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3-pip

# Fedora/RHEL
sudo dnf install python3-pip

# macOS (usually pre-installed)
python3 -m ensurepip --upgrade

# Then install dependencies
pip3 install -r requirements.txt
```

### Option 2: Use System Package Manager

If you're on Ubuntu/Debian, you can install some packages via apt:

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-requests \
    python3-tqdm \
    ffmpeg

# Then install remaining packages with pip
pip3 install -r requirements.txt
```

### Option 3: Use a Virtual Environment (Best Practice)

```bash
# Install venv if not available
sudo apt-get install python3-venv

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install packages
pip install -r requirements.txt

# Run the pipeline
python space_news_pipeline_optimized.py
```

## Required Packages

The pipeline needs these Python packages:
- openai (for script generation)
- requests (for API calls)
- feedparser (for RSS feeds)
- gTTS (for text-to-speech)
- tqdm (for progress bars)
- transformers (for fallback AI)
- torch (for Whisper)
- whisper (for transcription)
- supabase (for caching)
- python-dotenv (for environment variables)
- psutil (for resource management)

## Required System Tools

- **FFmpeg**: `sudo apt-get install ffmpeg`
- **Python 3.8+**: Already installed ✓

## Quick Test

After installing pip and dependencies, verify everything works:

```bash
python3 setup_check.py
```

This will check all requirements and tell you what's missing.

## Minimal Test (Without Dependencies)

If you want to test if the basic Python code is valid:

```bash
python3 -m py_compile space_news_pipeline_optimized.py
```

This checks for syntax errors without running the code.

## Need Help?

If you're on a managed/restricted system where you can't install packages:
1. Contact your system administrator
2. Request installation of the packages listed above
3. Or use a Docker container with all dependencies pre-installed
