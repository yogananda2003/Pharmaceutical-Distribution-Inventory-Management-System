import logging
import sys
import uuid
from contextvars import ContextVar
from typing import cast

import structlog

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")


def new_request_id() -> str:
    return str(uuid.uuid4())


def _add_context_ids(
    _logger: object, _method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    event_dict["request_id"] = request_id_ctx.get()
    event_dict["user_id"] = user_id_ctx.get()
    return event_dict


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_context_ids,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
