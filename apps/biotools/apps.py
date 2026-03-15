from django.apps import AppConfig


class BioToolsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.biotools"
    verbose_name = "bio.tools Integration"

    def ready(self):
        from .signals import connect_signals

        connect_signals()
