"""Allow ``python3 -m trading_common.cluster_state ...``."""
from .cli import main
import sys

sys.exit(main())
