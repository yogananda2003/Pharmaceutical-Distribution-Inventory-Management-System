from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "pharma_workers",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["app.workers.expiry_alerts"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
)
