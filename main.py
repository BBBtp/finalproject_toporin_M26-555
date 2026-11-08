"""ValutaTrade Hub command line entry point."""

from valutatrade_hub.cli.interface import main
from valutatrade_hub.logging_config import configure_logging

if __name__ == "__main__":
    configure_logging()
    raise SystemExit(main())
