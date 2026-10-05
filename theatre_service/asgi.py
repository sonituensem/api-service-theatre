"""ASGI config for Theatre Service API."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "theatre_service.settings")

application = get_asgi_application()
