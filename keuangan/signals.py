from django.db import transaction
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Import Models Baru
from core.utils import get_price_for
from gudang.models import Distribution, DistributionItem
from .models import Invoice, Payment

# ==========================================
# 1. AUTO-CREATE INVOICE (Saat Surat Jalan Terbit)
# ==========================================
def _compute_invoice_total(dist):
    """
    Hitung total tagihan invoice dari item distribusi.
    Prioritas: gunakan price_sell_snapshot (harga terkunci saat transaksi).
    Fallback ke master price jika snapshot belum terisi (data lama).
    """
    kab = getattr(getattr(dist.kios, 'kecamatan', None), 'kabupaten', None)
    total = Decimal('0')
    for item in dist.items.select_related('jenis_pupuk'):
        if item.price_sell_snapshot:
            harga_per_ton = item.price_sell_snapshot
        else:
            price_obj = get_price_for(item.jenis_pupuk, kab)
            harga_per_ton = price_obj.price_sell if price_obj else Decimal('0')
        total += (item.tonnage or Decimal('0')) * harga_per_ton
    return total


def _upsert_invoice(dist):
    if not dist.items.exists():
        return
    total_tagihan = _compute_invoice_total(dist)
    # Robust INV number: extract numeric suffix or generate from SJ number
    sj_num = dist.no_surat_jalan
    no_inv = sj_num.replace("SJ/", "INV/").replace("SJ-", "INV-") if "SJ" in sj_num else f"INV-{dist.id}"
    tgl_jatuh_tempo = dist.date + timedelta(days=7)

    invoice, created = Invoice.objects.get_or_create(
        distribution=dist,
        defaults={
            'inv_number': no_inv,
            'issue_date': dist.date,
            'due_date': tgl_jatuh_tempo,
            'total_amount': total_tagihan,
            'total_paid': Decimal('0'),
            'status': 'UNPAID',
        }
    )
    if not created:
        invoice.total_amount = total_tagihan
        invoice.issue_date = dist.date
        invoice.due_date = tgl_jatuh_tempo
        # update_status() sudah memanggil self.save() secara internal,
        # sehingga tidak perlu invoice.save() tambahan.
        invoice.update_status()


@receiver(post_save, sender=Distribution)
def create_invoice_automatis(sender, instance, created, **kwargs):
    # Jalankan setelah transaksi selesai supaya detail item sudah tersimpan
    def _safe_upsert(dist=instance):
        try:
            _upsert_invoice(dist)
        except Exception:
            logger.exception("Gagal upsert invoice untuk Distribution %s", dist.pk)
    transaction.on_commit(_safe_upsert)

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


@receiver(post_save, sender=DistributionItem)
def sync_invoice_on_item_save(sender, instance, created, **kwargs):
    """
    Sinkronisasi invoice saat item distribusi disimpan (edit/tambah via admin dll).
    Menggunakan on_commit agar invoice dihitung setelah semua perubahan selesai,
    menghindari kalkulasi berulang di tengah transaksi.
    """
    dist = instance.distribution
    def _safe_upsert(d=dist):
        try:
            _upsert_invoice(d)
        except Exception:
            logger.exception("Gagal sync invoice on item save untuk Distribution %s", d.pk)
    transaction.on_commit(_safe_upsert)


@receiver(post_delete, sender=DistributionItem)
def sync_invoice_on_item_delete(sender, instance, **kwargs):
    """Sinkronisasi invoice saat item distribusi dihapus."""
    dist = instance.distribution
    def _safe_upsert(d=dist):
        try:
            _upsert_invoice(d)
        except Exception:
            logger.exception("Gagal sync invoice on item delete untuk Distribution %s", d.pk)
    transaction.on_commit(_safe_upsert)