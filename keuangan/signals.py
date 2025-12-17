from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from datetime import timedelta
from core.models import FertilizerPrice
from gudang.models import Distribution
from .models import Invoice, Payment

# 1. AUTO-CREATE INVOICE saat Distribusi dibuat
@receiver(post_save, sender=Distribution)
def create_invoice_automatis(sender, instance, created, **kwargs):
    if created:
        # Cari harga master
        try:
            # Ambil jenis pupuk dari SO
            jenis_pupuk = instance.sales_order.fertilizer_type
            harga_obj = FertilizerPrice.objects.get(fertilizer_type=jenis_pupuk)
            harga_per_ton = harga_obj.price_sell
        except FertilizerPrice.DoesNotExist:
            harga_per_ton = 0
            
        total_tagihan = instance.tonnage_sent * harga_per_ton
        
        # Generate No Invoice (Ganti SJ jadi INV)
        no_inv = instance.surat_jalan_no.replace("SJ", "INV")
        
        # Hitung Jatuh Tempo (H+3 dari tgl kirim sesuai Video Rapat 1)
        tgl_jatuh_tempo = instance.transaction_date + timedelta(days=3)

        Invoice.objects.create(
            distribution=instance,
            invoice_no=no_inv,
            total_amount=total_tagihan,
            remaining_balance=total_tagihan, # Awalnya hutang full
            status='UNPAID',
            due_date=tgl_jatuh_tempo
        )

# 2. AUTO-UPDATE INVOICE saat ada Pembayaran Masuk
@receiver(post_save, sender=Payment)
def update_invoice_status(sender, instance, created, **kwargs):
    if created:
        invoice = instance.invoice
        # Tambahkan nominal bayar ke Invoice
        invoice.amount_paid += instance.amount
        invoice.save() # Logic status lunas/partial ada di method save() model Invoice

# 3. AUTO-UPDATE (Rollback) saat Pembayaran Dihapus
@receiver(post_delete, sender=Payment)
def rollback_invoice_status(sender, instance, **kwargs):
    invoice = instance.invoice
    invoice.amount_paid -= instance.amount
    invoice.save()