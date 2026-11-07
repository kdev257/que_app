from django.apps import AppConfig


class PrivacyConfig(AppConfig):
    name = 'privacy'
    verbose_name = 'Data Protection (DPDP)'

    def ready(self):
        from . import signals
        signals.connect_model_signals()
