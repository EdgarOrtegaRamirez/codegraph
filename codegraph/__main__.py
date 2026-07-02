"""Allow running codegraph as a module: python -m codegraph"""

from codegraph.cli import main
import sys

sys.exit(main())
