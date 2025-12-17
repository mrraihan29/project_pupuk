from django.apps import AppConfig

class KeuanganConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'keuangan'

    def ready(self):
        import keuangan.signals