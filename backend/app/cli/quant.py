"""python -m app.cli.quant   (also: python -m app.cli.pipeline quant)"""
import json

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import session_factory
from app.services import quant


def main() -> None:
    configure_logging(get_settings().log_level)
    with session_factory()() as s:
        print(json.dumps(quant.build_all(s), indent=1))


if __name__ == "__main__":
    main()
