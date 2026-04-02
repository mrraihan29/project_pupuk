"""
Test Suite — Verifikasi Fix Bug #1-#5 Integrasi Distribusi
==========================================================
Menguji keseluruhan flow:
  1. Distribusi baru  → stok & kuota terpotong tepat 1x per item
  2. Hapus distribusi → kuota di-restore tepat 1x
  3. Distribusi lama (tanpa items) → legacy signal tetap berfungsi
  4. Invoice             → tidak double-save, dihitung setelah commit
  5. StockCard cleanup   → tidak menghapus distribusi lain (SJ-1 vs SJ-10)
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.db import transaction
from django.db.models import Sum

from core.models import Kabupaten, Kecamatan, Kios, JenisPupuk, Armada, KiosAllocation, FertilizerPrice
from gudang.models import (
    SalesOrder, SalesOrderAllocation,
    Distribution, DistributionItem,
    StockCard, OrderNote, OrderNoteItem,
)
from keuangan.models import Invoice


# ── helper ──────────────────────────────────────────────────────────────
class _BaseTestMixin:
    """Shared fixtures untuk semua test case."""

    def _setup_master_data(self):
        self.kab = Kabupaten.objects.create(name='Semarang', code='SMG')
        self.kec = Kecamatan.objects.create(name='Ungaran', code='UNG', kabupaten=self.kab)
        self.kios = Kios.objects.create(
            name='Toko Tani Makmur', pic_name='Pak Budi',
            kecamatan=self.kec, address='Jl. Raya 1', phone='08123',
        )
        self.npk = JenisPupuk.objects.create(name='NPK', code='NPK')
        self.urea = JenisPupuk.objects.create(name='Urea', code='UREA')
        self.armada = Armada.objects.create(
            plate_number='H-1234-AB', vehicle_type='Engkel',
            driver_name='Supir A',
        )
        # Harga untuk invoice
        FertilizerPrice.objects.create(
            jenis_pupuk=self.npk, kabupaten=self.kab,
            price_buy=Decimal('5000000'), price_sell=Decimal('6000000'),
        )
        FertilizerPrice.objects.create(
            jenis_pupuk=self.urea, kabupaten=self.kab,
            price_buy=Decimal('4000000'), price_sell=Decimal('5000000'),
        )

    def _create_so_with_allocation(self, jenis, tonnage):
        """Buat SO + 1 alokasi → otomatis StockCard IN_SO via signal."""
        so = SalesOrder.objects.create(
            so_number=f'SO-{SalesOrder.objects.count()+1}',
            date=date(2026, 1, 1),
            jenis_pupuk=jenis,
        )
        SalesOrderAllocation.objects.create(
            sales_order=so, kecamatan=self.kec, tonnage=tonnage,
        )
        return so

    def _create_kios_allocation(self, jenis, quota):
        return KiosAllocation.objects.create(
            kios=self.kios, year=2026,
            jenis_pupuk=jenis,
            quota_original=quota,
            quota_remaining=quota,
        )

    def _physical_balance(self, jenis):
        agg = StockCard.objects.filter(
            jenis_pupuk=jenis, stock_type='PHYSICAL',
        ).aggregate(i=Sum('qty_in'), o=Sum('qty_out'))
        return (agg['i'] or Decimal('0')) - (agg['o'] or Decimal('0'))

    def _virtual_balance(self, jenis):
        agg = StockCard.objects.filter(
            jenis_pupuk=jenis, stock_type='VIRTUAL',
        ).aggregate(i=Sum('qty_in'), o=Sum('qty_out'))
        return (agg['i'] or Decimal('0')) - (agg['o'] or Decimal('0'))


# ════════════════════════════════════════════════════════════════════════
# TEST 1 — Bug #1: Distribusi baru TIDAK boleh double-deduct
# ════════════════════════════════════════════════════════════════════════
class TestBug1_NoDoubleDeduction(_BaseTestMixin, TestCase):
    """
    Skenario: Buat distribusi baru dengan 2 item (NPK 5T + Urea 3T).
    Expected: Kuota terpotong tepat 5T dan 3T, bukan 2x lipat.
    """

    def setUp(self):
        self._setup_master_data()
        self.so = self._create_so_with_allocation(self.npk, Decimal('100'))
        self.alloc_npk = self._create_kios_allocation(self.npk, Decimal('50'))
        self.alloc_urea = self._create_kios_allocation(self.urea, Decimal('30'))

    def test_single_item_distribution_quota(self):
        """1 item → kuota terpotong tepat 1x."""
        with transaction.atomic():
            dist = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='VIRTUAL', jenis_pupuk=self.npk,
                tonnage=Decimal('10'), source_so=self.so,
            )
            dist.save()

            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.npk,
                source_type='VIRTUAL', source_so=self.so,
                tonnage=Decimal('10'),
            )

        self.alloc_npk.refresh_from_db()
        # Kuota awal 50, dipotong 10 → sisa harus 40 (bukan 30 dari double-deduct)
        self.assertEqual(
            self.alloc_npk.quota_remaining, Decimal('40'),
            f"Kuota NPK seharusnya 40, tapi {self.alloc_npk.quota_remaining} "
            f"(kemungkinan double-deduct jika < 40)"
        )

    def test_multi_item_distribution_quota(self):
        """2 item berbeda jenis → masing-masing kuota terpotong 1x."""
        so_urea = self._create_so_with_allocation(self.urea, Decimal('50'))

        with transaction.atomic():
            dist = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='VIRTUAL', jenis_pupuk=self.npk,
                tonnage=Decimal('8'), source_so=self.so,
            )
            dist.save()

            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.npk,
                source_type='VIRTUAL', source_so=self.so,
                tonnage=Decimal('5'),
            )
            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.urea,
                source_type='VIRTUAL', source_so=so_urea,
                tonnage=Decimal('3'),
            )

        self.alloc_npk.refresh_from_db()
        self.alloc_urea.refresh_from_db()
        self.assertEqual(self.alloc_npk.quota_remaining, Decimal('45'),
                         "Kuota NPK harus 50-5=45")
        self.assertEqual(self.alloc_urea.quota_remaining, Decimal('27'),
                         "Kuota Urea harus 30-3=27")

    def test_stockcard_not_duplicated(self):
        """Tidak boleh ada legacy StockCard SJ-{id} untuk distribusi baru."""
        with transaction.atomic():
            dist = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='VIRTUAL', jenis_pupuk=self.npk,
                tonnage=Decimal('10'), source_so=self.so,
            )
            dist.save()

            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.npk,
                source_type='VIRTUAL', source_so=self.so,
                tonnage=Decimal('10'),
            )

        # Legacy card SJ-{id} (tanpa suffix item) TIDAK boleh ada
        legacy_count = StockCard.objects.filter(
            reference_number=f"SJ-{dist.id}"
        ).count()
        self.assertEqual(legacy_count, 0,
                         "Legacy StockCard SJ-{id} tidak boleh dibuat untuk distribusi baru")

        # Per-item cards HARUS ada (3 cards untuk VIRTUAL: V, P-IN, P-OUT)
        item = dist.items.first()
        per_item_count = StockCard.objects.filter(
            reference_number__startswith=f"SJ-{dist.id}-{item.id}-"
        ).count()
        self.assertEqual(per_item_count, 3,
                         "Harus ada 3 StockCard per-item untuk source VIRTUAL")


# ════════════════════════════════════════════════════════════════════════
# TEST 2 — Bug #2: Delete distribusi TIDAK boleh double-restore kuota
# ════════════════════════════════════════════════════════════════════════
class TestBug2_NoDoubleRestoreOnDelete(_BaseTestMixin, TestCase):

    def setUp(self):
        self._setup_master_data()
        self.so = self._create_so_with_allocation(self.npk, Decimal('100'))
        self.alloc_npk = self._create_kios_allocation(self.npk, Decimal('50'))

    def test_delete_restores_quota_exactly_once(self):
        """Buat distribusi, lalu hapus → kuota harus kembali ke semula."""
        with transaction.atomic():
            dist = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='VIRTUAL', jenis_pupuk=self.npk,
                tonnage=Decimal('10'), source_so=self.so,
            )
            dist.save()
            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.npk,
                source_type='VIRTUAL', source_so=self.so,
                tonnage=Decimal('10'),
            )

        # Setelah create: kuota = 50 - 10 = 40
        self.alloc_npk.refresh_from_db()
        self.assertEqual(self.alloc_npk.quota_remaining, Decimal('40'))

        # Hapus distribusi (CASCADE hapus items dulu)
        dist.delete()

        # Kuota harus kembali ke 50 (bukan 60 dari double-restore)
        self.alloc_npk.refresh_from_db()
        self.assertEqual(
            self.alloc_npk.quota_remaining, Decimal('50'),
            f"Kuota harus kembali ke 50 setelah delete, "
            f"tapi {self.alloc_npk.quota_remaining}"
        )

    def test_stockcards_cleaned_on_delete(self):
        """Semua StockCard terkait harus dihapus setelah distribusi dihapus."""
        with transaction.atomic():
            dist = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='VIRTUAL', jenis_pupuk=self.npk,
                tonnage=Decimal('10'), source_so=self.so,
            )
            dist.save()
            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.npk,
                source_type='VIRTUAL', source_so=self.so,
                tonnage=Decimal('10'),
            )

        dist_id = dist.id
        dist.delete()

        # Tidak boleh ada StockCard tersisa untuk distribusi ini
        remaining = StockCard.objects.filter(
            reference_number__startswith=f"SJ-{dist_id}-"
        ).count()
        self.assertEqual(remaining, 0, "Semua StockCard per-item harus dihapus")


# ════════════════════════════════════════════════════════════════════════
# TEST 3 — Bug #3 & #4: Invoice tidak double-save, dihitung dengan benar
# ════════════════════════════════════════════════════════════════════════
class TestBug3_InvoiceCreation(_BaseTestMixin, TestCase):

    def setUp(self):
        self._setup_master_data()
        self.so = self._create_so_with_allocation(self.npk, Decimal('100'))
        self.alloc_npk = self._create_kios_allocation(self.npk, Decimal('50'))

    def test_invoice_created_with_correct_total(self):
        """Invoice harus dibuat otomatis dengan total yang benar setelah distribusi."""
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                dist = Distribution(
                    date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                    kios=self.kios, armada=self.armada,
                    source_type='VIRTUAL', jenis_pupuk=self.npk,
                    tonnage=Decimal('10'), source_so=self.so,
                )
                dist.save()
                DistributionItem.objects.create(
                    distribution=dist, jenis_pupuk=self.npk,
                    source_type='VIRTUAL', source_so=self.so,
                    tonnage=Decimal('10'),
                )

        # Invoice dibuat via on_commit setelah atomic block
        self.assertTrue(
            Invoice.objects.filter(distribution=dist).exists(),
            "Invoice harus otomatis dibuat setelah distribusi"
        )
        inv = Invoice.objects.get(distribution=dist)
        # Harga NPK = 6.000.000/ton × 10 ton = 60.000.000
        expected = Decimal('10') * Decimal('6000000')
        self.assertEqual(inv.total_amount, expected,
                         f"Total invoice harus {expected}, tapi {inv.total_amount}")
        self.assertEqual(inv.status, 'UNPAID')

    def test_invoice_only_one_per_distribution(self):
        """Hanya 1 invoice per distribusi meskipun signal dipanggil berkali-kali."""
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                dist = Distribution(
                    date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                    kios=self.kios, armada=self.armada,
                    source_type='VIRTUAL', jenis_pupuk=self.npk,
                    tonnage=Decimal('15'), source_so=self.so,
                )
                dist.save()
                DistributionItem.objects.create(
                    distribution=dist, jenis_pupuk=self.npk,
                    source_type='VIRTUAL', source_so=self.so,
                    tonnage=Decimal('5'),
                )
                DistributionItem.objects.create(
                    distribution=dist, jenis_pupuk=self.npk,
                    source_type='VIRTUAL', source_so=self.so,
                    tonnage=Decimal('10'),
                )

        inv_count = Invoice.objects.filter(distribution=dist).count()
        self.assertEqual(inv_count, 1, "Harus tepat 1 invoice per distribusi")

        inv = Invoice.objects.get(distribution=dist)
        # 5 + 10 = 15 ton × 6.000.000 = 90.000.000
        expected = Decimal('15') * Decimal('6000000')
        self.assertEqual(inv.total_amount, expected)


# ════════════════════════════════════════════════════════════════════════
# TEST 4 — Bug #5: StockCard startswith collision
# ════════════════════════════════════════════════════════════════════════
class TestBug5_NoStartswithCollision(_BaseTestMixin, TestCase):

    def setUp(self):
        self._setup_master_data()
        self.so = self._create_so_with_allocation(self.npk, Decimal('200'))
        self.alloc_npk = self._create_kios_allocation(self.npk, Decimal('200'))

    def test_delete_dist_1_does_not_affect_dist_10(self):
        """Menghapus distribusi id=N tidak boleh menghapus StockCard distribusi id=N0."""
        # Buat distribusi pertama
        with transaction.atomic():
            dist1 = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='VIRTUAL', jenis_pupuk=self.npk,
                tonnage=Decimal('5'), source_so=self.so,
            )
            dist1.save()
            DistributionItem.objects.create(
                distribution=dist1, jenis_pupuk=self.npk,
                source_type='VIRTUAL', source_so=self.so,
                tonnage=Decimal('5'),
            )

        # Buat banyak distribusi agar ID naik
        dists_to_create = []
        for i in range(15):
            with transaction.atomic():
                d = Distribution(
                    date=date(2026, 1, 16), pkp_date=date(2026, 1, 16),
                    kios=self.kios, armada=self.armada,
                    source_type='VIRTUAL', jenis_pupuk=self.npk,
                    tonnage=Decimal('1'), source_so=self.so,
                )
                d.save()
                DistributionItem.objects.create(
                    distribution=d, jenis_pupuk=self.npk,
                    source_type='VIRTUAL', source_so=self.so,
                    tonnage=Decimal('1'),
                )
                dists_to_create.append(d)

        # Cari distribusi yang id-nya dimulai dengan digit yang sama dengan dist1
        # Misal dist1.id = 1, cari dist yang id = 10, 11, dst.
        dist1_id = dist1.id
        potentially_colliding = [d for d in dists_to_create
                                 if str(d.id).startswith(str(dist1_id))
                                 and d.id != dist1_id]

        if not potentially_colliding:
            # Jika tidak ada collision candidate, skip test
            self.skipTest("Tidak ada ID yang bisa collision (jarang terjadi)")

        target_dist = potentially_colliding[0]
        target_item = target_dist.items.first()
        target_ref = f"SJ-{target_dist.id}-{target_item.id}-P-OUT"

        # Pastikan StockCard target ada sebelum delete
        self.assertTrue(
            StockCard.objects.filter(reference_number=target_ref).exists(),
            f"StockCard {target_ref} harus ada sebelum delete"
        )

        # Hapus dist1
        dist1.delete()

        # StockCard target distribusi lain HARUS masih ada
        self.assertTrue(
            StockCard.objects.filter(reference_number=target_ref).exists(),
            f"StockCard {target_ref} TIDAK boleh ikut terhapus saat delete dist {dist1_id}"
        )


# ════════════════════════════════════════════════════════════════════════
# TEST 5 — Legacy distribution (tanpa items) tetap berfungsi
# ════════════════════════════════════════════════════════════════════════
class TestLegacyDistribution(_BaseTestMixin, TestCase):
    """
    Distribusi lama yang tidak punya DistributionItem (legacy data).
    Saat di-EDIT, legacy signal harus tetap berjalan.
    """

    def setUp(self):
        self._setup_master_data()
        self.so = self._create_so_with_allocation(self.npk, Decimal('100'))
        self.alloc_npk = self._create_kios_allocation(self.npk, Decimal('50'))

    def test_legacy_edit_updates_stockcard(self):
        """Edit distribusi lama (tanpa items) → legacy signal update StockCard."""
        # Simulasi distribusi lama: buat langsung tanpa items
        # Karena created=True SKIP signal, kita perlu simulate legacy data
        dist = Distribution(
            date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
            kios=self.kios, armada=self.armada,
            source_type='VIRTUAL', jenis_pupuk=self.npk,
            tonnage=Decimal('10'), source_so=self.so,
        )
        dist.save()  # created=True → skip signal (correct)

        # Sekarang manually create legacy StockCard (simulating old data)
        StockCard.objects.create(
            date=date(2026, 1, 15), jenis_pupuk=self.npk,
            stock_type='VIRTUAL', transaction_type='OUT_DIST_V',
            reference_number=f"SJ-{dist.id}",
            description='Legacy card', qty_in=0, qty_out=Decimal('10'),
        )
        # Manually adjust quota (simulating old behavior)
        self.alloc_npk.quota_remaining -= Decimal('10')
        self.alloc_npk.save()

        # Pastikan tidak ada items
        self.assertFalse(dist.items.exists())

        # Edit: ubah tonnage
        dist.tonnage = Decimal('15')
        dist.save()  # created=False, items.exists()=False → legacy signal runs

        # Legacy StockCard harus terupdate
        legacy_card = StockCard.objects.get(reference_number=f"SJ-{dist.id}")
        self.assertEqual(legacy_card.qty_out, Decimal('15'),
                         "Legacy StockCard harus diupdate saat edit distribusi lama")


# ════════════════════════════════════════════════════════════════════════
# TEST 6 — End-to-end: Catatan Order → Distribusi → Stok & Kuota
# ════════════════════════════════════════════════════════════════════════
class TestEndToEndFlow(_BaseTestMixin, TestCase):
    """Full integration test: Order → Distribusi → verify stok & kuota."""

    def setUp(self):
        self._setup_master_data()
        self.so = self._create_so_with_allocation(self.npk, Decimal('100'))
        self.alloc_npk = self._create_kios_allocation(self.npk, Decimal('50'))

    def test_order_to_distribution_flow(self):
        """
        1. Buat OrderNote + OrderNoteItem (10 ton NPK)
        2. Buat Distribution + DistributionItem (kirim 6 ton)
        3. Verifikasi sisa pesanan = 4 ton
        4. Verifikasi kuota terpotong tepat 6 ton
        5. Verifikasi stok virtual terpotong tepat 6 ton
        """
        # Step 1: Buat catatan order
        order = OrderNote.objects.create(
            date=date(2026, 1, 10), kecamatan=self.kec, kios=self.kios,
        )
        order_item = OrderNoteItem.objects.create(
            order=order, jenis_pupuk=self.npk, tonnage=Decimal('10'),
        )

        # Step 2: Buat distribusi
        with transaction.atomic():
            dist = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='VIRTUAL', jenis_pupuk=self.npk,
                tonnage=Decimal('6'), source_so=self.so,
            )
            dist.save()
            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.npk,
                source_type='VIRTUAL', source_so=self.so,
                tonnage=Decimal('6'), order_item=order_item,
            )

        # Step 3: Sisa pesanan
        order_item.refresh_from_db()
        self.assertEqual(order_item.remaining_tonnage, Decimal('4'),
                         "Sisa pesanan harus 10 - 6 = 4 ton")

        # Step 4: Kuota
        self.alloc_npk.refresh_from_db()
        self.assertEqual(self.alloc_npk.quota_remaining, Decimal('44'),
                         "Kuota harus 50 - 6 = 44 ton")

        # Step 5: Virtual balance SO
        self.so.refresh_from_db()
        virtual_bal = self.so.get_virtual_balance()
        self.assertEqual(virtual_bal, Decimal('94'),
                         "Virtual balance SO harus 100 - 6 = 94 ton")

    def test_physical_source_distribution(self):
        """Distribusi dari gudang fisik → hanya potong stok fisik."""
        # Transfer dulu ke gudang fisik
        from gudang.models import WarehouseTransfer
        WarehouseTransfer.objects.create(
            source_so=self.so, date=date(2026, 1, 10),
            tonnage=Decimal('20'), reference_code='SJ-PABRIK-001',
        )

        phys_before = self._physical_balance(self.npk)
        self.assertEqual(phys_before, Decimal('20'), "Stok fisik harus 20 setelah transfer")

        # Distribusi dari fisik
        with transaction.atomic():
            dist = Distribution(
                date=date(2026, 1, 15), pkp_date=date(2026, 1, 15),
                kios=self.kios, armada=self.armada,
                source_type='PHYSICAL', jenis_pupuk=self.npk,
                tonnage=Decimal('8'),
            )
            dist.save()
            DistributionItem.objects.create(
                distribution=dist, jenis_pupuk=self.npk,
                source_type='PHYSICAL', tonnage=Decimal('8'),
            )

        # Stok fisik: 20 masuk - 8 keluar = 12
        phys_after = self._physical_balance(self.npk)
        self.assertEqual(phys_after, Decimal('12'),
                         f"Stok fisik harus 20-8=12, tapi {phys_after}")

        # Kuota tetap terpotong
        self.alloc_npk.refresh_from_db()
        self.assertEqual(self.alloc_npk.quota_remaining, Decimal('42'),
                         "Kuota harus 50-8=42")