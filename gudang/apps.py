from django.apps import AppConfig

class GudangConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gudang'

    def ready(self):
        # Import signals agar aktif saat aplikasi berjalan
        import gudang.signals