import os
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=root_dir / ".env")

CENTREON_BASE_URL = os.getenv("CENTREON_BASE_URL")
CENTREON_USERNAME = os.getenv("CENTREON_USERNAME")
CENTREON_PASSWORD = os.getenv("CENTREON_PASSWORD")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL"))