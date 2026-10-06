"""WSGI config for Theatre Service API."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "theatre_service.settings")

application = get_wsgi_application()
