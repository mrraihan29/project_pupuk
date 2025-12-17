from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SalesOrder, StockCard, Distribution

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
        
@receiver(post_save, sender=Distribution)
def create_outbound_stock_card(sender, instance, created, **kwargs):
    """
    Otomatis mencatat transaksi 'OUT' di Kartu Stok saat Distribusi dibuat.
    """
    if created:
        # PERBAIKAN BUG SALDO (Race Condition Fix)
        # Masalah: Saat signal ini jalan, stok di SalesOrder BELUM dikurangi di database.
        # Solusi: Kita hitung manual saldo akhirnya di sini.
        
        current_stock_db = instance.sales_order.tonnage_current # Masih 10.00
        sent_qty = instance.tonnage_sent                        # 2.00
        
        # Hitung saldo real
        real_balance = current_stock_db - sent_qty              # 8.00

        StockCard.objects.create(
            sales_order=instance.sales_order,
            trx_type='OUT', # Tipe Keluar
            reference_number=instance.surat_jalan_no,
            qty_change=sent_qty,
            balance_after=real_balance # <-- MENGGUNAKAN HASIL HITUNGAN MANUAL
        )