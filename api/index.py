"""
Vercel Serverless Entry Point
Exports the FastAPI app for Vercel's Python runtime.
"""
import sys
import os

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set Vercel flag before importing server
os.environ["VERCEL"] = "1"

from server import app
