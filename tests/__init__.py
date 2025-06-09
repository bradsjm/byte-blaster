"""Test package for the byte_blaster library."""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(project_root))
