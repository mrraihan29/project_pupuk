from django.db.models.signals import post_save, post_delete
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
            harga_per_ton = harga_obj.price_sell * 1000
            
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
# 2. AUTO-UPDATE STATUS (Saat Ada Pembayaran)
# ==========================================
@receiver(post_save, sender=Payment)
def update_invoice_status(sender, instance, created, **kwargs):
    if created:
        invoice = instance.invoice
        # Tambahkan nominal bayar ke Invoice
        # Field di model baru adalah 'total_paid'
        invoice.total_paid += instance.amount
        
        # Panggil method update_status() di model Invoice untuk cek Lunas/Belum
        invoice.update_status() 

# ==========================================
# 3. ROLLBACK (Saat Pembayaran Dihapus)
# ==========================================
@receiver(post_delete, sender=Payment)
def rollback_invoice_status(sender, instance, **kwargs):
    invoice = instance.invoice
    invoice.total_paid -= instance.amount
    
    # Cek status lagi setelah dikurangi
    if invoice.total_paid <= 0:
        invoice.total_paid = 0
        invoice.status = 'UNPAID'
    elif invoice.total_paid < invoice.total_amount:
        invoice.status = 'PARTIAL'
        
    invoice.save()