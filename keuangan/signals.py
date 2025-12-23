from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from datetime import timedelta
from decimal import Decimal

# Import Models Baru
from core.models import FertilizerPrice
from gudang.models import Distribution
from .models import Invoice, Payment

# ==========================================
# 1. AUTO-CREATE INVOICE (Saat Surat Jalan Terbit)
# ==========================================
@receiver(post_save, sender=Distribution)
def create_invoice_automatis(sender, instance, created, **kwargs):
    if created:
        # A. CARI HARGA JUAL
        try:
            # FIX: Ambil jenis_pupuk langsung dari Distribution (bukan dari SO)
            # Karena transaksi Fisik tidak punya SO, tapi pasti punya jenis_pupuk
            harga_obj = FertilizerPrice.objects.get(jenis_pupuk=instance.jenis_pupuk)
            
            # Konversi Harga: Di Master Harga per KG, di sini Tonase
            # 1 Ton = 1000 KG
            harga_per_ton = harga_obj.price_sell
            
        except FertilizerPrice.DoesNotExist:
            harga_per_ton = 0
            
        # B. HITUNG TOTAL TAGIHAN
        total_tagihan = instance.tonnage * harga_per_ton
        
        # C. GENERATE NO INVOICE (Ganti SJ jadi INV)
        no_inv = instance.no_surat_jalan.replace("SJ", "INV")
        
        # D. TENTUKAN JATUH TEMPO (Default H+7 atau sesuai kebijakan)
        tgl_jatuh_tempo = instance.date + timedelta(days=7)

        # E. SIMPAN INVOICE
        # Perhatikan nama field disesuaikan dengan keuangan/models.py baru
        Invoice.objects.create(
            distribution=instance,
            inv_number=no_inv,          # Field baru (dulu invoice_no)
            issue_date=instance.date,   # Field baru
            due_date=tgl_jatuh_tempo,
            total_amount=total_tagihan,
            total_paid=0,               # Default 0
            status='UNPAID'
        )

# ==========================================
# 2. SIMPAN STATE LAMA (untuk deteksi perubahan status/nominal)
# ==========================================
@receiver(pre_save, sender=Payment)
def stash_old_payment(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_status = None
        instance._old_amount = None
        return

    try:
        old = Payment.objects.get(pk=instance.pk)
        instance._old_status = old.status
        instance._old_amount = old.amount
    except Payment.DoesNotExist:
        instance._old_status = None
        instance._old_amount = None


# 3. AUTO-UPDATE STATUS (Saat Ada Pembayaran)
# ==========================================
@receiver(post_save, sender=Payment)
def update_invoice_status(sender, instance, created, **kwargs):
    invoice = instance.invoice
    old_status = getattr(instance, '_old_status', None)
    old_amount = getattr(instance, '_old_amount', None)

    delta = Decimal('0')

    if created:
        if instance.status == 'APPROVED':
            delta += instance.amount
    else:
        if old_status == 'APPROVED' and instance.status == 'APPROVED':
            if old_amount is not None and instance.amount != old_amount:
                delta += instance.amount - old_amount
        elif old_status == 'APPROVED' and instance.status != 'APPROVED':
            delta -= old_amount if old_amount is not None else instance.amount
        elif old_status != 'APPROVED' and instance.status == 'APPROVED':
            delta += instance.amount

    if delta:
        invoice.total_paid = max(Decimal('0'), invoice.total_paid + delta)
        invoice.update_status()


# ==========================================
# 4. ROLLBACK (Saat Pembayaran Dihapus)
# ==========================================
@receiver(post_delete, sender=Payment)
def rollback_invoice_status(sender, instance, **kwargs):
    if instance.status != 'APPROVED':
        return

    invoice = instance.invoice
    invoice.total_paid = max(Decimal('0'), invoice.total_paid - instance.amount)
    
    # Cek status lagi setelah dikurangi
    if invoice.total_paid <= 0:
        invoice.total_paid = 0
        invoice.status = 'UNPAID'
    elif invoice.total_paid < invoice.total_amount:
        invoice.status = 'PARTIAL'
        
    invoice.save()