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

# Bootstrap GCP Service Account credentials from environment variable to /tmp file
import os
import json
gcp_json = os.getenv('GCP_SERVICE_ACCOUNT_JSON')
if gcp_json:
    try:
        # Validate that it is a valid JSON
        json.loads(gcp_json)
        # Write to /tmp/bigquery-key.json
        tmp_path = "/tmp/bigquery-key.json"
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(gcp_json)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = tmp_path
        print(f"✓ GCP Credentials bootstrapped to {tmp_path}")
    except Exception as e:
        print(f"⚠ Failed to bootstrap GCP credentials: {e}")
else:
    # If GOOGLE_APPLICATION_CREDENTIALS points to a non-existent file (e.g. on Vercel),
    # remove it so google-auth doesn't crash.
    env_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if env_creds and not os.path.exists(env_creds):
        del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
        print("⚠ Removed invalid GOOGLE_APPLICATION_CREDENTIALS environment variable")

# Import the FastAPI app instance from src.api.main
from api.main import app
