"""
Vercel Serverless Function wrapper for ASCII Stego
"""

import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app

# Vercel expects 'app' or 'handler'
handler = app
