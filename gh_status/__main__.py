# gh_status/__main__.py
import sys

import dotenv

from gh_status.cli import main

dotenv.load_dotenv()

if __name__ == "__main__":
    sys.exit(main())