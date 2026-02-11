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
from core.utils import get_price_for
from core.models import KiosAllocation


def _get_stock_balance(jenis_id, stock_type):
    """Helper: hitung saldo stok terkini dari StockCard ledger."""
    agg = StockCard.objects.filter(
        jenis_pupuk_id=jenis_id, stock_type=stock_type
    ).aggregate(total_in=Sum('qty_in'), total_out=Sum('qty_out'))
    return (agg['total_in'] or Decimal('0')) - (agg['total_out'] or Decimal('0'))


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
@receiver(pre_save, sender=WarehouseTransfer)
def cache_old_transfer(sender, instance, **kwargs):
    """Cache state lama Transfer agar post_save bisa recompute SO/jenis lama."""
    if not instance.pk:
        instance._old_trf_state = None
    else:
        try:
            old = WarehouseTransfer.objects.get(pk=instance.pk)
            instance._old_trf_state = {
                'source_so_id': old.source_so_id,
                'jenis_id': old.source_so.jenis_pupuk_id if old.source_so else None,
            }
        except WarehouseTransfer.DoesNotExist:
            instance._old_trf_state = None


@receiver(post_save, sender=WarehouseTransfer)
def update_stock_from_transfer(sender, instance, created, **kwargs):
    """
    Saat 'Tarik ke Gudang' disimpan:
    1. Buat Kartu Stok VIRTUAL OUT (Mengurangi stok pabrik)
    2. Buat Kartu Stok PHYSICAL IN (Menambah stok gudang)
    """
    # Safety net: cek sisa virtual balance sebelum create/update kartu stok
    virtual_balance = instance.source_so.get_virtual_balance()
    if created and virtual_balance < 0:
        raise ValueError(
            f"Stok virtual SO {instance.source_so.so_number} tidak cukup! "
            f"Sisa: {virtual_balance + instance.tonnage:,.2f} Ton."
        )

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
                'description': f"Pengisian Stok Fisik (SO: {instance.source_so.so_number})",
                'qty_in': instance.tonnage,
                'qty_out': 0,
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
                'description': f"Pengisian Stok Fisik (SO: {instance.source_so.so_number})",
                'qty_in': instance.tonnage,
                'qty_out': 0,
            }
        )

    # Recompute OLD SO/jenis jika source_so berubah
    prev_trf = getattr(instance, '_old_trf_state', None)
    if prev_trf and prev_trf['source_so_id'] != instance.source_so_id:
        if prev_trf['jenis_id']:
            recompute_stock_balance(prev_trf['jenis_id'], 'VIRTUAL')
            recompute_stock_balance(prev_trf['jenis_id'], 'PHYSICAL')
        old_so = SalesOrder.objects.filter(pk=prev_trf['source_so_id']).first()
        if old_so:
            update_so_closure(old_so)

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
    LEGACY handler untuk distribusi TANPA detail items (data lama).
    Distribusi baru selalu menggunakan DistributionItem → signal per-item
    yang menangani StockCard dan kuota secara mandiri.

    Guard:
    1. created=True  → skip, items akan disimpan setelah ini dan signal
       per-item yang menangani stok & kuota.
    2. items.exists() → skip, per-item signal sudah aktif.
    """
    if created:
        return  # Items belum ada saat header baru disimpan; per-item signal akan handle
    # Jika sudah pakai detail items, stock & quota ditangani di signal DistributionItem
    if instance.items.exists():
        return
    ref_code = f"SJ-{instance.id}"
    
    # Tentukan Tipe Transaksi & Stok
    if instance.source_type == 'VIRTUAL':
        trans_type = 'OUT_DIST_V'
        stk_type = 'VIRTUAL'
        desc = f"Kirim Langsung ke {instance.kios.name} (Dari GPP)"
    else:
        trans_type = 'OUT_DIST_P'
        stk_type = 'PHYSICAL'
        desc = f"Kirim ke {instance.kios.name} (Gudang PUD)"

    # Gabungkan semua operasi (StockCard + recompute + quota) dalam satu atomic block
    # agar tidak ada inkonsistensi jika salah satu gagal.
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

        # Update kuota kios
        prev = getattr(instance, '_old_dist_state', None)
        if prev:
            adjust_quota(prev['kios_id'], prev['jenis_id'], prev['year'], prev['tonnage'])
        adjust_quota(instance.kios_id, instance.jenis_pupuk_id, instance.date.year, -instance.tonnage)

@receiver(post_delete, sender=Distribution)
def delete_stock_from_distribution(sender, instance, **kwargs):
    """
    LEGACY delete handler.
    Saat Distribution dihapus (CASCADE), Django menghapus DistributionItem
    terlebih dahulu — signal per-item sudah me-restore kuota & hapus StockCard.
    
    Untuk menghindari double-restore kuota, kita cek apakah legacy StockCard
    (ref SJ-{id}) masih ada. Jika tidak ada, artinya distribusi ini
    menggunakan per-item flow dan kuota sudah di-restore oleh signal item.
    """
    legacy_ref = f"SJ-{instance.id}"
    legacy_exists = StockCard.objects.filter(reference_number=legacy_ref).exists()

    # Bersihkan semua StockCard terkait distribusi ini:
    # - Legacy card: exact match "SJ-{id}"
    # - Per-item cards: prefix "SJ-{id}-" (dengan trailing dash agar tidak
    #   menghapus distribusi lain, misal SJ-1 vs SJ-10)
    StockCard.objects.filter(reference_number=legacy_ref).delete()
    StockCard.objects.filter(reference_number__startswith=f"SJ-{instance.id}-").delete()

    if not legacy_exists:
        # Per-item signals sudah handle restore kuota & recompute balance
        # Cukup recompute saldo akhir saja untuk memastikan konsistensi
        recompute_stock_balance(instance.jenis_pupuk_id, 'PHYSICAL')
        if instance.source_type == 'VIRTUAL':
            recompute_stock_balance(instance.jenis_pupuk_id, 'VIRTUAL')
            if instance.source_so:
                update_so_closure(instance.source_so)
        return

    # === LEGACY PATH: distribusi lama tanpa items ===
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
    else:
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

    # === PRICE LOCKING: Isi harga snapshot saat pertama kali disimpan ===
    # Harga di-lock saat transaksi dibuat agar laporan historis tidak berubah
    # ketika master price diupdate di kemudian hari.
    # EDIT FIX: Jika jenis_pupuk berubah, reset snapshot agar harga baru terisi.
    if instance._old_state and instance.jenis_pupuk_id != instance._old_state['jenis_id']:
        instance.price_sell_snapshot = None
        instance.price_buy_snapshot = None
    if instance.price_sell_snapshot is None or instance.price_buy_snapshot is None:
        kab = getattr(
            getattr(instance.distribution.kios, 'kecamatan', None),
            'kabupaten', None
        )
        price_obj = get_price_for(instance.jenis_pupuk, kab)
        if price_obj:
            if instance.price_sell_snapshot is None:
                instance.price_sell_snapshot = price_obj.price_sell
            if instance.price_buy_snapshot is None:
                instance.price_buy_snapshot = price_obj.price_buy


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
    dist = instance.distribution

    # ── 1. DEFINISI KEY (Konsisten) ──
    ref_virtual = f"SJ-{instance.distribution_id}-{instance.id}-V"
    ref_pin     = f"SJ-{instance.distribution_id}-{instance.id}-P-IN"
    ref_pout    = f"SJ-{instance.distribution_id}-{instance.id}-P-OUT"

    pkp_date = dist.pkp_date or dist.date

    with transaction.atomic():
        # ── VALIDASI STOK (Safety net) ──
        prev = getattr(instance, '_old_state', None)
        old_tonnage = prev['tonnage'] if prev else Decimal('0')
        delta = instance.tonnage - old_tonnage

        if delta > 0:
            if instance.source_type == 'VIRTUAL' and instance.source_so:
                vbal = instance.source_so.get_virtual_balance()
                if created:
                    pass  # get_virtual_balance sudah memperhitungkan item ini via query
                if vbal < 0:
                    raise ValueError(
                        f"Stok virtual SO {instance.source_so.so_number} tidak cukup!"
                    )
            elif instance.source_type == 'PHYSICAL':
                phys_bal = _get_stock_balance(instance.jenis_pupuk_id, 'PHYSICAL')
                if phys_bal - delta < 0:
                    raise ValueError(
                        f"Stok fisik {instance.jenis_pupuk.code} tidak cukup! "
                        f"Sisa: {phys_bal:,.2f} Ton, diminta tambahan {delta:,.2f} Ton."
                    )

        # ── 2. JIKA SOURCE == 'VIRTUAL' ──
        if instance.source_type == 'VIRTUAL':
            so_number = instance.source_so.so_number if instance.source_so else '-'

            # 2a. Virtual OUT — kurangi stok pabrik
            StockCard.objects.update_or_create(
                reference_number=ref_virtual,
                defaults={
                    'date': dist.date,
                    'jenis_pupuk': instance.jenis_pupuk,
                    'stock_type': 'VIRTUAL',
                    'transaction_type': 'OUT_DIST_V',
                    'description': f"Distribusi ke {dist.kios.name} (SO: {so_number})",
                    'qty_in': 0,
                    'qty_out': instance.tonnage,
                }
            )

            # 2b. Physical IN (Manipulasi) — barang "mampir" masuk gudang administrasi
            StockCard.objects.update_or_create(
                reference_number=ref_pin,
                defaults={
                    'date': dist.date,
                    'jenis_pupuk': instance.jenis_pupuk,
                    'stock_type': 'PHYSICAL',
                    'transaction_type': 'IN_DIST_P',
                    'description': f"Pengisian Stok Fisik (SO: {so_number})",
                    'qty_in': instance.tonnage,
                    'qty_out': 0,
                }
            )

            # 2c. Physical OUT (Manipulasi) — keluar ke kios
            StockCard.objects.update_or_create(
                reference_number=ref_pout,
                defaults={
                    'date': pkp_date,
                    'jenis_pupuk': instance.jenis_pupuk,
                    'stock_type': 'PHYSICAL',
                    'transaction_type': 'OUT_DIST_P',
                    'description': f"Distribusi ke {dist.kios.name} (SO: {so_number})",
                    'qty_in': 0,
                    'qty_out': instance.tonnage,
                }
            )

        # ── 3. JIKA SOURCE == 'PHYSICAL' ──
        else:
            # 3a. Cleanup — hapus Virtual & Physical IN jika ada
            #     (aman jika user mengubah tipe dari Virtual ke Fisik)
            StockCard.objects.filter(
                reference_number__in=[ref_virtual, ref_pin]
            ).delete()

            # 3b. Physical OUT — stok gudang keluar ke kios
            StockCard.objects.update_or_create(
                reference_number=ref_pout,
                defaults={
                    'date': pkp_date,
                    'jenis_pupuk': instance.jenis_pupuk,
                    'stock_type': 'PHYSICAL',
                    'transaction_type': 'OUT_DIST_P',
                    'description': f"Distribusi ke {dist.kios.name} (Gudang PUD)",
                    'qty_in': 0,
                    'qty_out': instance.tonnage,
                }
            )

        # ── RECOMPUTE BALANCE & KUOTA ──
        prev = getattr(instance, '_old_state', None)
        if prev:
            prev_virtual = prev['source_type'] == 'VIRTUAL'
            if prev_virtual:
                recompute_stock_balance(prev['jenis_id'], 'VIRTUAL')
            recompute_stock_balance(prev['jenis_id'], 'PHYSICAL')
            _apply_quota(instance.distribution, prev['jenis_id'], prev['tonnage'])
            if prev['source_type'] == 'VIRTUAL' and prev['source_so_id']:
                update_so_closure(SalesOrder.objects.filter(pk=prev['source_so_id']).first())

        if instance.source_type == 'VIRTUAL':
            recompute_stock_balance(instance.jenis_pupuk_id, 'VIRTUAL')
        recompute_stock_balance(instance.jenis_pupuk_id, 'PHYSICAL')
        _apply_quota(instance.distribution, instance.jenis_pupuk_id, -instance.tonnage)
        if instance.source_type == 'VIRTUAL' and instance.source_so:
            update_so_closure(instance.source_so)


@receiver(post_delete, sender=DistributionItem)
def delete_stock_from_distribution_item(sender, instance, **kwargs):
    ref_virtual = f"SJ-{instance.distribution_id}-{instance.id}-V"
    ref_pin = f"SJ-{instance.distribution_id}-{instance.id}-P-IN"
    ref_pout = f"SJ-{instance.distribution_id}-{instance.id}-P-OUT"
    StockCard.objects.filter(reference_number__in=[ref_virtual, ref_pin, ref_pout]).delete()
    try:
        with transaction.atomic():
            if instance.source_type == 'VIRTUAL':
                recompute_stock_balance(instance.jenis_pupuk_id, 'VIRTUAL')
            recompute_stock_balance(instance.jenis_pupuk_id, 'PHYSICAL')
            _apply_quota(instance.distribution, instance.jenis_pupuk_id, instance.tonnage)
            if instance.source_type == 'VIRTUAL' and instance.source_so:
                update_so_closure(instance.source_so)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            "Error saat restore kuota/stok untuk DistributionItem %s: %s",
            instance.id, e
        )