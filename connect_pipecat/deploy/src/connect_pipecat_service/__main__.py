import logging

import uvicorn

from .app import build_app
from .config import settings


def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    uvicorn.run(
        build_app(settings), host=settings.host, port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == '__main__':
    main()
