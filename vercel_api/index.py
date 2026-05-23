import sys
from pathlib import Path

# Add src directory and project root to system path
sys.path.insert(0, str((Path(__file__).parent.parent / "src").resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

# Set UTF-8 encoding for stdout/stderr to prevent UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Import the FastAPI app instance from src.api.main
from api.main import app
