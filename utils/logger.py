import logging
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
log_file = parent_dir / "crawler.log"
logging.basicConfig(filename=log_file, level=logging.INFO, format="%(asctime)s - %(levelname)s:\n%(message)s\n")

logger = logging

