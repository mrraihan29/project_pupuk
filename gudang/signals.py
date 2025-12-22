from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal

from .models import (
    SalesOrder, SalesOrderAllocation, 
    WarehouseTransfer, Distribution, 
    StockCard
)

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

@receiver(post_delete, sender=WarehouseTransfer)
def delete_stock_from_transfer(sender, instance, **kwargs):
    """Jika data transfer dihapus, hapus juga kartu stoknya"""
    StockCard.objects.filter(reference_number__startswith=f"TRF-{instance.id}-").delete()

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

@receiver(post_delete, sender=Distribution)
def delete_stock_from_distribution(sender, instance, **kwargs):
    StockCard.objects.filter(reference_number=f"SJ-{instance.id}").delete()