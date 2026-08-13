"""
pytest conftest.py for detection tests.
Ensures ai-engine root is on the Python path.
"""
import sys
import os

# Add ai-engine root to path so 'detection' package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
