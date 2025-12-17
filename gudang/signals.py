from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SalesOrder, StockCard

@receiver(post_save, sender=SalesOrder)
def create_initial_stock_card(sender, instance, created, **kwargs):
    """
    Otomatis mencatat transaksi 'IN' di Kartu Stok saat SO baru dibuat.
    """
    if created: # Hanya jalan jika ini data BARU (bukan edit)
        StockCard.objects.create(
            sales_order=instance,
            trx_type='IN', # Tipe Masuk
            reference_number=f"Penebusan Awal - {instance.so_code}",
            qty_change=instance.tonnage_initial,
            balance_after=instance.tonnage_initial # Saldo awal = Tonase awal
        )