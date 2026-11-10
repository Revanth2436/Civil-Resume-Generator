import sys
from pathlib import Path

# Locate application source directories
REPO_ROOT = Path(__file__).resolve().parent.parent
SUBDIR = REPO_ROOT / "resume-Creator-New-main" / "Mail-Resume_Automation-main - Copy" / "Mail-Resume_Automation-main"

if SUBDIR.exists() and str(SUBDIR) not in sys.path:
    sys.path.insert(0, str(SUBDIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import app
