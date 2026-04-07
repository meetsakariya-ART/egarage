"""
core/apps.py
─────────────
Registers signals when Django starts.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'eGarage Core'

    def ready(self):
        """Import signals so they are registered."""
        import core.signals  # noqa