from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal

from .models import (
    SalesOrder, SalesOrderAllocation, 
    WarehouseTransfer, Distribution, DistributionItem,
    StockCard
)
from core.models import KiosAllocation


def recompute_stock_balance(jenis_id, stock_type):
    """Re-hit total saldo per jenis & tipe stok sehingga field balance tidak misleading."""
    if not jenis_id or not stock_type:
        return
    with transaction.atomic():
        cards = list(
            StockCard.objects.select_for_update()
            .filter(jenis_pupuk_id=jenis_id, stock_type=stock_type)
            .order_by('date', 'created_at', 'id')
        )

        running = Decimal('0')
        for card in cards:
            running += (card.qty_in or Decimal('0')) - (card.qty_out or Decimal('0'))
            if card.balance != running:
                StockCard.objects.filter(pk=card.pk).update(balance=running)


def update_so_closure(so):
    """Auto-close/open SO berdasar saldo virtual aktual."""
    if not so:
        return
    try:
        with transaction.atomic():
            so_ref = SalesOrder.objects.select_for_update().get(pk=so.pk)
            balance = so_ref.get_virtual_balance()
            should_close = balance <= Decimal('0')
            if so_ref.is_closed != should_close:
                so_ref.is_closed = should_close
                so_ref.save(update_fields=['is_closed'])
    except SalesOrder.DoesNotExist:
        return

# ==========================================
# A. OTOMATISASI PENEBUSAN (SO) -> STOK VIRTUAL MASUK
# ==========================================
@receiver(post_save, sender=SalesOrderAllocation)
@receiver(post_delete, sender=SalesOrderAllocation)
def update_stock_from_allocation(sender, instance, **kwargs):
    """
    Setiap kali Alokasi Kecamatan ditambah/diubah/dihapus,
    Update total 'Stok Virtual Masuk' di Kartu Stok milik SO tersebut.
    """
    so = instance.sales_order
    
    # 1. Hitung Ulang Total SO ini dari semua alokasinya
    total_qty = so.allocations.aggregate(total=Sum('tonnage'))['total'] or Decimal('0')
    
    # 2. Cari atau Buat Kartu Stok untuk SO ini
    # Kode Referensi: SO-{ID}
    ref_code = f"SO-{so.id}"
    
    # Gunakan atomic transaction agar aman
    with transaction.atomic():
        card, created = StockCard.objects.get_or_create(
            reference_number=ref_code,
            transaction_type='IN_SO',
            defaults={
                'date': so.date,
                'jenis_pupuk': so.jenis_pupuk,
                'stock_type': 'VIRTUAL',
                'description': f"Penebusan {so.so_number}",
                'qty_in': total_qty,
                'qty_out': 0,
                'balance': 0 # Nanti dihitung ulang
            }
        )
        
        # Jika update (bukan baru buat), update nilainya
        if not created:
            card.qty_in = total_qty
            card.date = so.date
            card.jenis_pupuk = so.jenis_pupuk # Jaga-jaga kalau SO ganti jenis
            card.save()

    recompute_stock_balance(so.jenis_pupuk_id, 'VIRTUAL')
    update_so_closure(so)

# ==========================================
# B. OTOMATISASI TRANSFER -> VIRTUAL OUT & FISIK IN
# ==========================================
@receiver(post_save, sender=WarehouseTransfer)
def update_stock_from_transfer(sender, instance, created, **kwargs):
    """
    Saat 'Tarik ke Gudang' disimpan:
    1. Buat Kartu Stok VIRTUAL OUT (Mengurangi stok pabrik)
    2. Buat Kartu Stok PHYSICAL IN (Menambah stok gudang)
    """
    with transaction.atomic():
        # KARTU 1: VIRTUAL OUT
        ref_v = f"TRF-{instance.id}-V"
        StockCard.objects.update_or_create(
            reference_number=ref_v,
            defaults={
                'date': instance.date,
                'jenis_pupuk': instance.source_so.jenis_pupuk,
                'stock_type': 'VIRTUAL',
                'transaction_type': 'OUT_TRF',
                'description': f"Ditarik ke Gudang (Ref: {instance.reference_code})",
                'qty_in': 0,
                'qty_out': instance.tonnage,
            }
        )

        # KARTU 2: PHYSICAL IN
        ref_p = f"TRF-{instance.id}-P"
        StockCard.objects.update_or_create(
            reference_number=ref_p,
            defaults={
                'date': instance.date,
                'jenis_pupuk': instance.source_so.jenis_pupuk,
                'stock_type': 'PHYSICAL',
                'transaction_type': 'IN_TRF',
                'description': f"Masuk dari SO {instance.source_so.so_number}",
                'qty_in': instance.tonnage,
                'qty_out': 0,
            }
        )

    recompute_stock_balance(instance.source_so.jenis_pupuk_id, 'VIRTUAL')
    recompute_stock_balance(instance.source_so.jenis_pupuk_id, 'PHYSICAL')
    update_so_closure(instance.source_so)

@receiver(post_delete, sender=WarehouseTransfer)
def delete_stock_from_transfer(sender, instance, **kwargs):
    """Jika data transfer dihapus, hapus juga kartu stoknya"""
    StockCard.objects.filter(reference_number__startswith=f"TRF-{instance.id}-").delete()
    recompute_stock_balance(instance.source_so.jenis_pupuk_id, 'VIRTUAL')
    recompute_stock_balance(instance.source_so.jenis_pupuk_id, 'PHYSICAL')
    update_so_closure(instance.source_so)

# ==========================================
# C. OTOMATISASI DISTRIBUSI -> STOK KELUAR
# ==========================================
@receiver(post_save, sender=Distribution)
def update_stock_from_distribution(sender, instance, created, **kwargs):
    """
    Saat Surat Jalan dibuat:
    - Jika VIRTUAL: Catat OUT_DIST_V
    - Jika PHYSICAL: Catat OUT_DIST_P
    """
    # Jika sudah pakai detail items, stock & quota ditangani di signal DistributionItem
    if instance.items.exists():
        return
    ref_code = f"SJ-{instance.id}"
    
    # Tentukan Tipe Transaksi & Stok
    if instance.source_type == 'VIRTUAL':
        trans_type = 'OUT_DIST_V'
        stk_type = 'VIRTUAL'
        desc = f"Kirim Langsung ke {instance.kios.name} (Dari Pabrik)"
    else:
        trans_type = 'OUT_DIST_P'
        stk_type = 'PHYSICAL'
        desc = f"Kirim ke {instance.kios.name} (Dari Gudang)"

    StockCard.objects.update_or_create(
        reference_number=ref_code,
        defaults={
            'date': instance.date,
            'jenis_pupuk': instance.jenis_pupuk,
            'stock_type': stk_type,
            'transaction_type': trans_type,
            'description': desc,
            'qty_in': 0,
            'qty_out': instance.tonnage,
        }
    )

    prev = getattr(instance, '_old_dist_state', None)
    if prev:
        recompute_stock_balance(prev['jenis_id'], prev['stock_type'])
        if prev['source_type'] == 'VIRTUAL' and prev['source_so_id']:
            update_so_closure(SalesOrder.objects.filter(pk=prev['source_so_id']).first())

    recompute_stock_balance(instance.jenis_pupuk_id, stk_type)
    if instance.source_type == 'VIRTUAL' and instance.source_so:
        update_so_closure(instance.source_so)

    # Update kuota kios (kurangi sesuai tonase)
    def adjust_quota(kios_id, jenis_id, year, delta):
        alloc = KiosAllocation.objects.select_for_update().filter(
            kios_id=kios_id, jenis_pupuk_id=jenis_id, year=year
        ).first()
        if not alloc:
            raise ValueError("Alokasi kios tidak ditemukan saat update distribusi")
        alloc.quota_remaining += delta
        if alloc.quota_remaining < 0:
            raise ValueError("Kuota kios menjadi negatif, batalkan transaksi")
        alloc.save(update_fields=['quota_remaining'])

    with transaction.atomic():
        prev = getattr(instance, '_old_dist_state', None)
        # Jika update, kembalikan tonase lama ke alokasi sebelumnya
        if prev:
            adjust_quota(prev['kios_id'], prev['jenis_id'], prev['year'], prev['tonnage'])
        # Kurangi kuota pada alokasi baru
        adjust_quota(instance.kios_id, instance.jenis_pupuk_id, instance.date.year, -instance.tonnage)

@receiver(post_delete, sender=Distribution)
def delete_stock_from_distribution(sender, instance, **kwargs):
    if instance.items.exists():
        # Stock handled by DistributionItem signals; ensure header stockcards removed if any legacy
        StockCard.objects.filter(reference_number__startswith=f"SJ-{instance.id}").delete()
        return
    StockCard.objects.filter(reference_number=f"SJ-{instance.id}").delete()
    try:
        with transaction.atomic():
            alloc = KiosAllocation.objects.select_for_update().filter(
                kios=instance.kios,
                jenis_pupuk=instance.jenis_pupuk,
                year=instance.date.year
            ).first()
            if alloc:
                alloc.quota_remaining += instance.tonnage
                alloc.save(update_fields=['quota_remaining'])
    except Exception:
        pass

    recompute_stock_balance(instance.jenis_pupuk_id, 'PHYSICAL' if instance.source_type == 'PHYSICAL' else 'VIRTUAL')
    if instance.source_type == 'VIRTUAL' and instance.source_so:
        update_so_closure(instance.source_so)


@receiver(pre_save, sender=Distribution)
def cache_old_distribution(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = Distribution.objects.get(pk=instance.pk)
        instance._old_dist_state = {
            'kios_id': old.kios_id,
            'jenis_id': old.jenis_pupuk_id,
            'year': old.date.year,
            'tonnage': old.tonnage,
            'stock_type': 'PHYSICAL' if old.source_type == 'PHYSICAL' else 'VIRTUAL',
            'source_type': old.source_type,
            'source_so_id': old.source_so_id,
        }
    except Distribution.DoesNotExist:
        instance._old_dist_state = None


# === NEW: PER-ITEM STOCK & KUOTA ===

@receiver(pre_save, sender=DistributionItem)
def cache_old_distribution_item(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_state = None
        return
    try:
        old = DistributionItem.objects.get(pk=instance.pk)
        instance._old_state = {
            'jenis_id': old.jenis_pupuk_id,
            'tonnage': old.tonnage,
            'source_type': old.source_type,
            'source_so_id': old.source_so_id,
        }
    except DistributionItem.DoesNotExist:
        instance._old_state = None


def _apply_quota(distribution, jenis_id, ton_delta):
    alloc = KiosAllocation.objects.select_for_update().filter(
        kios=distribution.kios,
        jenis_pupuk_id=jenis_id,
        year=distribution.date.year
    ).first()
    if not alloc:
        raise ValueError("Alokasi kios tidak ditemukan saat update distribusi")
    alloc.quota_remaining += ton_delta
    if alloc.quota_remaining < 0:
        raise ValueError("Kuota kios menjadi negatif, batalkan transaksi")
    alloc.save(update_fields=['quota_remaining'])


@receiver(post_save, sender=DistributionItem)
def update_stock_from_distribution_item(sender, instance, created, **kwargs):
    ref_code = f"SJ-{instance.distribution_id}-{instance.id}"
    stock_type = 'VIRTUAL' if instance.source_type == 'VIRTUAL' else 'PHYSICAL'
    trans_type = 'OUT_DIST_V' if stock_type == 'VIRTUAL' else 'OUT_DIST_P'
    desc = f"Kirim ke {instance.distribution.kios.name} ({stock_type.title()})"

    with transaction.atomic():
        StockCard.objects.update_or_create(
            reference_number=ref_code,
            defaults={
                'date': instance.distribution.date,
                'jenis_pupuk': instance.jenis_pupuk,
                'stock_type': stock_type,
                'transaction_type': trans_type,
                'description': desc,
                'qty_in': 0,
                'qty_out': instance.tonnage,
            }
        )

        prev = getattr(instance, '_old_state', None)
        if prev:
            # Kembalikan stok/quota lama
            prev_stock_type = 'VIRTUAL' if prev['source_type'] == 'VIRTUAL' else 'PHYSICAL'
            recompute_stock_balance(prev['jenis_id'], prev_stock_type)
            _apply_quota(instance.distribution, prev['jenis_id'], prev['tonnage'])
            if prev['source_type'] == 'VIRTUAL' and prev['source_so_id']:
                update_so_closure(SalesOrder.objects.filter(pk=prev['source_so_id']).first())

        # Kurangi stok/quota baru
        recompute_stock_balance(instance.jenis_pupuk_id, stock_type)
        _apply_quota(instance.distribution, instance.jenis_pupuk_id, -instance.tonnage)
        if instance.source_type == 'VIRTUAL' and instance.source_so:
            update_so_closure(instance.source_so)


@receiver(post_delete, sender=DistributionItem)
def delete_stock_from_distribution_item(sender, instance, **kwargs):
    ref_code = f"SJ-{instance.distribution_id}-{instance.id}"
    StockCard.objects.filter(reference_number=ref_code).delete()
    try:
        with transaction.atomic():
            stock_type = 'VIRTUAL' if instance.source_type == 'VIRTUAL' else 'PHYSICAL'
            recompute_stock_balance(instance.jenis_pupuk_id, stock_type)
            _apply_quota(instance.distribution, instance.jenis_pupuk_id, instance.tonnage)
            if instance.source_type == 'VIRTUAL' and instance.source_so:
                update_so_closure(instance.source_so)
    except Exception:
        pass