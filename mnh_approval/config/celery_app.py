import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mnh_approval.settings")

app = Celery("mnh_approval")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()