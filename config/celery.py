"""
Celery Application
==================
Celery handles all asynchronous tasks — primarily email dispatch.
The beat scheduler runs periodic tasks (e.g. stale draft cleanup).
"""
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("denbi_registry")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
