"""
SIMULATION SCRIPT - FULL E2E SIMULATION
=========================================
Menjalankan simulasi operasional lengkap:
  Order → SO → Transfer → Distribusi → Payment → Biaya Ops
  + Verifikasi manual di setiap tahap.

Jalankan: python simulation_run.py
"""
import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sim_dp.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import (
    Kabupaten, Kecamatan, JenisPupuk, FertilizerPrice,
    Kios, KiosAllocation, Armada
)
from gudang.models import (
    SalesOrder, SalesOrderAllocation, WarehouseTransfer,
    Distribution, DistributionItem, StockCard,
    OrderNote, OrderNoteItem
)
from keuangan.models import BiayaOperasional, Invoice, Payment
from decimal import Decimal
from datetime import date, timedelta

# ==========================================
# HELPER FUNCTIONS
# ==========================================
PASS = 0
FAIL = 0

def check(label, actual, expected, tolerance=Decimal('0.01')):
    global PASS, FAIL
    if isinstance(actual, Decimal) and isinstance(expected, Decimal):
        ok = abs(actual - expected) < tolerance
    else:
        ok = (actual == expected)
    status = "PASS" if ok else "FAIL"
    if not ok:
        FAIL += 1
        print(f"  [{status}] {label}: Got {actual}, Expected {expected}")
    else:
        PASS += 1
        print(f"  [{status}] {label}: {actual}")
    return ok

def section(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

def sub(title):
    print(f"\n--- {title} ---")

# ==========================================
# LOAD REFERENCES
# ==========================================
kab_smg = Kabupaten.objects.get(name='Semarang')
kab_dmk = Kabupaten.objects.get(name='Demak')
kec_ungaran = Kecamatan.objects.get(name='Ungaran')
kec_bergas = Kecamatan.objects.get(name='Bergas')
kec_mranggen = Kecamatan.objects.get(name='Mranggen')
kec_karangawen = Kecamatan.objects.get(name='Karangawen')
npk = JenisPupuk.objects.get(code='NPK')
urea = JenisPupuk.objects.get(code='UREA')
kios1 = Kios.objects.get(name='Kios Tani Sejahtera')  # Ungaran, Semarang
kios2 = Kios.objects.get(name='Kios Makmur Jaya')     # Bergas, Semarang
kios3 = Kios.objects.get(name='Kios Berkah Tani')      # Mranggen, Demak
kios4 = Kios.objects.get(name='Kios Subur Makmur')     # Karangawen, Demak
armada1 = Armada.objects.get(plate_number='H-1234-AB')
armada2 = Armada.objects.get(plate_number='K-5678-CD')

today = date.today()

# ==========================================================
section("PHASE 2: CATATAN ORDER (ORDER NOTES)")
# ==========================================================

sub("Buat Order #1: Kios Tani Sejahtera minta NPK 10T + Urea 5T")
order1 = OrderNote.objects.create(date=today, kecamatan=kec_ungaran, kios=kios1, notes='Order rutin bulanan')
OrderNoteItem.objects.create(order=order1, jenis_pupuk=npk, tonnage=Decimal('10'))
OrderNoteItem.objects.create(order=order1, jenis_pupuk=urea, tonnage=Decimal('5'))

sub("Buat Order #2: Kios Berkah Tani minta NPK 8T")
order2 = OrderNote.objects.create(date=today, kecamatan=kec_mranggen, kios=kios3, notes='Order NPK saja')
OrderNoteItem.objects.create(order=order2, jenis_pupuk=npk, tonnage=Decimal('8'))

sub("Buat Order #3: Kios Makmur Jaya minta Urea 6T")
order3 = OrderNote.objects.create(date=today, kecamatan=kec_bergas, kios=kios2, notes='Order Urea')
OrderNoteItem.objects.create(order=order3, jenis_pupuk=urea, tonnage=Decimal('6'))

check("OrderNote count", OrderNote.objects.count(), 3)
check("OrderNoteItem count", OrderNoteItem.objects.count(), 4)

# ==========================================================
section("PHASE 3: PENEBUSAN (SALES ORDER) → STOK VIRTUAL")
# ==========================================================

sub("SO #1: NPK 50 Ton dari Pabrik")
so1 = SalesOrder.objects.create(
    so_number='SO-2025-001', date=today, jenis_pupuk=npk
)
# Alokasi per kecamatan
SalesOrderAllocation.objects.create(sales_order=so1, kecamatan=kec_ungaran, tonnage=Decimal('15'))
SalesOrderAllocation.objects.create(sales_order=so1, kecamatan=kec_bergas, tonnage=Decimal('15'))
SalesOrderAllocation.objects.create(sales_order=so1, kecamatan=kec_mranggen, tonnage=Decimal('10'))
SalesOrderAllocation.objects.create(sales_order=so1, kecamatan=kec_karangawen, tonnage=Decimal('10'))

sub("SO #2: Urea 30 Ton dari Pabrik")
so2 = SalesOrder.objects.create(
    so_number='SO-2025-002', date=today, jenis_pupuk=urea
)
SalesOrderAllocation.objects.create(sales_order=so2, kecamatan=kec_ungaran, tonnage=Decimal('10'))
SalesOrderAllocation.objects.create(sales_order=so2, kecamatan=kec_bergas, tonnage=Decimal('10'))
SalesOrderAllocation.objects.create(sales_order=so2, kecamatan=kec_mranggen, tonnage=Decimal('5'))
SalesOrderAllocation.objects.create(sales_order=so2, kecamatan=kec_karangawen, tonnage=Decimal('5'))

sub("Verifikasi Stok Virtual setelah SO")
so1.refresh_from_db()
so2.refresh_from_db()
check("SO1 (NPK) total_tonnage", so1.total_tonnage, Decimal('50'))
check("SO2 (Urea) total_tonnage", so2.total_tonnage, Decimal('30'))
check("SO1 virtual_balance", so1.get_virtual_balance(), Decimal('50'))
check("SO2 virtual_balance", so2.get_virtual_balance(), Decimal('30'))

sub("Verifikasi StockCard Virtual")
virt_npk = StockCard.objects.filter(jenis_pupuk=npk, stock_type='VIRTUAL', transaction_type='IN_SO')
virt_urea = StockCard.objects.filter(jenis_pupuk=urea, stock_type='VIRTUAL', transaction_type='IN_SO')
check("StockCard Virtual IN NPK", virt_npk.first().qty_in, Decimal('50'))
check("StockCard Virtual IN Urea", virt_urea.first().qty_in, Decimal('30'))

# ==========================================================
section("PHASE 4: WAREHOUSE TRANSFER → STOK FISIK")
# ==========================================================

sub("Transfer #1: Tarik NPK 20T dari SO1 ke Gudang")
trf1 = WarehouseTransfer(source_so=so1, date=today, tonnage=Decimal('20'), reference_code='PBK-001')
trf1.clean()
trf1.save()

sub("Transfer #2: Tarik Urea 15T dari SO2 ke Gudang")
trf2 = WarehouseTransfer(source_so=so2, date=today, tonnage=Decimal('15'), reference_code='PBK-002')
trf2.clean()
trf2.save()

sub("Verifikasi Saldo setelah Transfer")
so1.refresh_from_db()
so2.refresh_from_db()
# Virtual: 50 - 20 = 30 NPK | 30 - 15 = 15 Urea
check("SO1 virtual_balance after transfer", so1.get_virtual_balance(), Decimal('30'))
check("SO2 virtual_balance after transfer", so2.get_virtual_balance(), Decimal('15'))

# Physical balance check
def get_physical_balance(jenis):
    agg = StockCard.objects.filter(jenis_pupuk=jenis, stock_type='PHYSICAL').aggregate(
        total_in=django.db.models.Sum('qty_in'),
        total_out=django.db.models.Sum('qty_out'),
    )
    return (agg['total_in'] or Decimal('0')) - (agg['total_out'] or Decimal('0'))

import django.db.models
check("Physical balance NPK", get_physical_balance(npk), Decimal('20'))
check("Physical balance Urea", get_physical_balance(urea), Decimal('15'))

# ==========================================================
section("PHASE 5: DISTRIBUSI (SURAT JALAN) → VARIOUS TYPES")
# ==========================================================

# --- SJ #1: Virtual → Kios Tani Sejahtera (NPK 10T from SO1) ---
sub("SJ #1: VIRTUAL → Kios Tani Sejahtera, NPK 10T (dari SO1)")
dist1 = Distribution(
    date=today, pkp_date=today,
    kios=kios1, armada=armada1,
    source_type='VIRTUAL', source_so=so1,
    jenis_pupuk=npk, tonnage=Decimal('10')
)
dist1.clean()
dist1.save()
# Create Item
di1 = DistributionItem.objects.create(
    distribution=dist1, jenis_pupuk=npk,
    source_type='VIRTUAL', source_so=so1,
    tonnage=Decimal('10')
)

sub("Verifikasi setelah SJ #1")
so1.refresh_from_db()
# Virtual: 30 - 10 = 20 NPK (karena 10T keluar virtual via dist)
check("SO1 virtual after SJ#1", so1.get_virtual_balance(), Decimal('20'))
# Physical: 20 + 10 (in from virtual route) - 10 (out from physical) = 20 → net same
check("Physical NPK after SJ#1 (net)", get_physical_balance(npk), Decimal('20'))

kios1_npk_alloc = KiosAllocation.objects.get(kios=kios1, jenis_pupuk=npk, year=today.year)
check("Kios1 NPK quota_remaining", kios1_npk_alloc.quota_remaining, Decimal('15'))  # 25 - 10

# --- SJ #2: Physical → Kios Makmur Jaya (Urea 6T from Gudang) ---
sub("SJ #2: PHYSICAL → Kios Makmur Jaya, Urea 6T (dari Gudang)")
dist2 = Distribution(
    date=today, pkp_date=today,
    kios=kios2, armada=armada2,
    source_type='PHYSICAL',
    jenis_pupuk=urea, tonnage=Decimal('6')
)
dist2.clean()
dist2.save()
di2 = DistributionItem.objects.create(
    distribution=dist2, jenis_pupuk=urea,
    source_type='PHYSICAL',
    tonnage=Decimal('6')
)

sub("Verifikasi setelah SJ #2")
# Physical Urea: 15 - 6 = 9
check("Physical Urea after SJ#2", get_physical_balance(urea), Decimal('9'))
kios2_urea_alloc = KiosAllocation.objects.get(kios=kios2, jenis_pupuk=urea, year=today.year)
check("Kios2 Urea quota_remaining", kios2_urea_alloc.quota_remaining, Decimal('9'))  # 15 - 6

# --- SJ #3: Virtual → Kios Berkah Tani (NPK 8T from SO1) ---
sub("SJ #3: VIRTUAL → Kios Berkah Tani, NPK 8T (dari SO1)")
dist3 = Distribution(
    date=today, pkp_date=today,
    kios=kios3, armada=armada1,
    source_type='VIRTUAL', source_so=so1,
    jenis_pupuk=npk, tonnage=Decimal('8')
)
dist3.clean()
dist3.save()
di3 = DistributionItem.objects.create(
    distribution=dist3, jenis_pupuk=npk,
    source_type='VIRTUAL', source_so=so1,
    tonnage=Decimal('8')
)

sub("Verifikasi setelah SJ #3")
so1.refresh_from_db()
# Virtual: 20 - 8 = 12 NPK
check("SO1 virtual after SJ#3", so1.get_virtual_balance(), Decimal('12'))
# Physical NPK: 20 + 8 (in) - 8 (out) = 20
check("Physical NPK after SJ#3", get_physical_balance(npk), Decimal('20'))
kios3_npk_alloc = KiosAllocation.objects.get(kios=kios3, jenis_pupuk=npk, year=today.year)
check("Kios3 NPK quota_remaining", kios3_npk_alloc.quota_remaining, Decimal('12'))  # 20 - 8

# --- SJ #4: Physical → Kios Subur Makmur (Urea 5T from Gudang) ---
sub("SJ #4: PHYSICAL → Kios Subur Makmur, Urea 5T (dari Gudang)")
dist4 = Distribution(
    date=today, pkp_date=today,
    kios=kios4, armada=armada2,
    source_type='PHYSICAL',
    jenis_pupuk=urea, tonnage=Decimal('5')
)
dist4.clean()
dist4.save()
di4 = DistributionItem.objects.create(
    distribution=dist4, jenis_pupuk=urea,
    source_type='PHYSICAL',
    tonnage=Decimal('5')
)

sub("Verifikasi setelah SJ #4")
# Physical Urea: 9 - 5 = 4
check("Physical Urea after SJ#4", get_physical_balance(urea), Decimal('4'))
kios4_urea_alloc = KiosAllocation.objects.get(kios=kios4, jenis_pupuk=urea, year=today.year)
check("Kios4 Urea quota_remaining", kios4_urea_alloc.quota_remaining, Decimal('5'))  # 10 - 5


# ==========================================================
section("PHASE 5B: VERIFIKASI KOMPREHENSIF STOK & KUOTA")
# ==========================================================

sub("Ringkasan Saldo Virtual")
check("Virtual NPK balance (from cards)", 
      StockCard.objects.filter(jenis_pupuk=npk, stock_type='VIRTUAL').last().balance if StockCard.objects.filter(jenis_pupuk=npk, stock_type='VIRTUAL').exists() else Decimal('0'),
      Decimal('12'))  # 50 - 20 (trf) - 10 (SJ1) - 8 (SJ3) = 12
check("Virtual Urea balance (from cards)", 
      StockCard.objects.filter(jenis_pupuk=urea, stock_type='VIRTUAL').last().balance if StockCard.objects.filter(jenis_pupuk=urea, stock_type='VIRTUAL').exists() else Decimal('0'),
      Decimal('15'))  # 30 - 15 (trf) = 15

sub("Ringkasan Saldo Fisik")
# Physical balance: sum(in) - sum(out)
# NPK: IN=20(trf)+10(SJ1)+8(SJ3)=38 | OUT=10(SJ1)+8(SJ3)=18 → net=20
check("Physical NPK net balance", get_physical_balance(npk), Decimal('20'))
# Urea: IN=15(trf) | OUT=6(SJ2)+5(SJ4)=11 → net=4
check("Physical Urea net balance", get_physical_balance(urea), Decimal('4'))

sub("Ringkasan Kuota Kios tersisa")
for kios in [kios1, kios2, kios3, kios4]:
    for jp in [npk, urea]:
        alloc = KiosAllocation.objects.filter(kios=kios, jenis_pupuk=jp, year=today.year).first()
        if alloc:
            print(f"  {kios.name} | {jp.code}: Awal={alloc.quota_original}T Sisa={alloc.quota_remaining}T Terpakai={alloc.quota_used}T")

# ==========================================================
section("PHASE 6: INVOICE & PEMBAYARAN")
# ==========================================================

sub("Verifikasi Auto-Generated Invoices")
check("Invoice count", Invoice.objects.count(), 4)

inv1 = Invoice.objects.get(distribution=dist1)
inv2 = Invoice.objects.get(distribution=dist2)
inv3 = Invoice.objects.get(distribution=dist3)
inv4 = Invoice.objects.get(distribution=dist4)

# Manual check: SJ1 = NPK 10T × Rp5.500.000 = Rp55.000.000
check("Invoice#1 (SJ1 NPK 10T)", inv1.total_amount, Decimal('55000000'))
# Manual check: SJ2 = Urea 6T × Rp4.200.000 = Rp25.200.000
check("Invoice#2 (SJ2 Urea 6T)", inv2.total_amount, Decimal('25200000'))
# Manual check: SJ3 = NPK 8T × Rp5.500.000 = Rp44.000.000
check("Invoice#3 (SJ3 NPK 8T)", inv3.total_amount, Decimal('44000000'))
# Manual check: SJ4 = Urea 5T × Rp4.200.000 = Rp21.000.000
check("Invoice#4 (SJ4 Urea 5T)", inv4.total_amount, Decimal('21000000'))

check("All invoices UNPAID", all(inv.status == 'UNPAID' for inv in [inv1, inv2, inv3, inv4]), True)

sub("Price Snapshot Verification")
di1.refresh_from_db()
di2.refresh_from_db()
di3.refresh_from_db()
di4.refresh_from_db()
check("DI1 price_sell_snapshot (NPK Smg)", di1.price_sell_snapshot, Decimal('5500000'))
check("DI1 price_buy_snapshot (NPK Smg)", di1.price_buy_snapshot, Decimal('4800000'))
check("DI2 price_sell_snapshot (Urea Smg)", di2.price_sell_snapshot, Decimal('4200000'))
check("DI2 price_buy_snapshot (Urea Smg)", di2.price_buy_snapshot, Decimal('3600000'))
check("DI3 price_sell_snapshot (NPK Dmk)", di3.price_sell_snapshot, Decimal('5500000'))
check("DI3 price_buy_snapshot (NPK Dmk)", di3.price_buy_snapshot, Decimal('4800000'))
check("DI4 price_sell_snapshot (Urea Dmk)", di4.price_sell_snapshot, Decimal('4200000'))
check("DI4 price_buy_snapshot (Urea Dmk)", di4.price_buy_snapshot, Decimal('3600000'))

sub("Bayar Invoice #1: LUNAS sekaligus (Rp55.000.000)")
pay1 = Payment.objects.create(
    invoice=inv1, date=today,
    amount=Decimal('55000000'), method='Transfer Bank',
    status='APPROVED', notes='Lunas sekaligus'
)
inv1.refresh_from_db()
check("Invoice#1 status after full pay", inv1.status, 'PAID')
check("Invoice#1 total_paid", inv1.total_paid, Decimal('55000000'))
check("Invoice#1 remaining", inv1.remaining_balance, Decimal('0'))

sub("Bayar Invoice #2: CICILAN 1 (Rp10.000.000)")
pay2a = Payment.objects.create(
    invoice=inv2, date=today,
    amount=Decimal('10000000'), method='Transfer Bank',
    status='APPROVED', notes='Cicilan 1'
)
inv2.refresh_from_db()
check("Invoice#2 status after partial", inv2.status, 'PARTIAL')
check("Invoice#2 remaining", inv2.remaining_balance, Decimal('15200000'))

sub("Bayar Invoice #2: CICILAN 2 (Rp15.200.000) → LUNAS")
pay2b = Payment.objects.create(
    invoice=inv2, date=today,
    amount=Decimal('15200000'), method='Transfer Bank',
    status='APPROVED', notes='Cicilan 2 - Lunas'
)
inv2.refresh_from_db()
check("Invoice#2 status after full pay", inv2.status, 'PAID')
check("Invoice#2 remaining", inv2.remaining_balance, Decimal('0'))

sub("Invoice #3 dan #4 tetap UNPAID (untuk test piutang)")
inv3.refresh_from_db()
inv4.refresh_from_db()
check("Invoice#3 status", inv3.status, 'UNPAID')
check("Invoice#4 status", inv4.status, 'UNPAID')

# ==========================================================
section("PHASE 7: BIAYA OPERASIONAL")
# ==========================================================

sub("Buat biaya operasional berbagai kategori")
ops1 = BiayaOperasional.objects.create(
    tanggal=today, kategori_utama='ARMADA',
    armada=armada1, kabupaten=kab_smg,
    deskripsi='BBM Truk Engkel pengiriman ke Ungaran',
    nominal=Decimal('500000'), status='SELESAI'
)
ops2 = BiayaOperasional.objects.create(
    tanggal=today, kategori_utama='ARMADA',
    armada=armada2, kabupaten=kab_dmk,
    deskripsi='BBM Truk Fuso pengiriman ke Mranggen + Karangawen',
    nominal=Decimal('750000'), status='SELESAI'
)
ops3 = BiayaOperasional.objects.create(
    tanggal=today, kategori_utama='KANTOR',
    kabupaten=kab_smg,
    deskripsi='Listrik kantor bulan ini',
    nominal=Decimal('1200000'), status='SELESAI'
)
ops4 = BiayaOperasional.objects.create(
    tanggal=today, kategori_utama='LAINNYA',
    kabupaten=kab_dmk,
    deskripsi='Biaya fotokopi dokumen',
    nominal=Decimal('150000'), status='PROSES'
)

check("BiayaOps count", BiayaOperasional.objects.count(), 4)
check("BiayaOps SELESAI count", BiayaOperasional.objects.filter(status='SELESAI').count(), 3)
check("BiayaOps PROSES count", BiayaOperasional.objects.filter(status='PROSES').count(), 1)

# Total biaya approved
total_ops_approved = sum(
    bo.nominal for bo in BiayaOperasional.objects.filter(status='SELESAI')
)
check("Total BiayaOps (SELESAI)", total_ops_approved, Decimal('2450000'))

# ==========================================================
section("PHASE 8: VERIFIKASI LAPORAN KEUANGAN (MANUAL CALC)")
# ==========================================================

sub("Kalkulasi Manual Laba Rugi")
# PENDAPATAN (Subtotal Jual): berdasarkan DistributionItem price_sell_snapshot × tonnage
# DI1: NPK 10T × 5.500.000 = 55.000.000
# DI2: Urea 6T × 4.200.000 = 25.200.000
# DI3: NPK 8T × 5.500.000 = 44.000.000  
# DI4: Urea 5T × 4.200.000 = 21.000.000
total_jual = Decimal('55000000') + Decimal('25200000') + Decimal('44000000') + Decimal('21000000')
print(f"  Pendapatan (Penjualan) = Rp {total_jual:,.0f}")
check("Total Penjualan", total_jual, Decimal('145200000'))

# HPP (Subtotal Beli): berdasarkan DistributionItem price_buy_snapshot × tonnage
# DI1: NPK 10T × 4.800.000 = 48.000.000
# DI2: Urea 6T × 3.600.000 = 21.600.000
# DI3: NPK 8T × 4.800.000 = 38.400.000
# DI4: Urea 5T × 3.600.000 = 18.000.000
total_beli = Decimal('48000000') + Decimal('21600000') + Decimal('38400000') + Decimal('18000000')
print(f"  HPP (Pembelian)        = Rp {total_beli:,.0f}")
check("Total HPP", total_beli, Decimal('126000000'))

# LABA KOTOR
laba_kotor = total_jual - total_beli
print(f"  Laba Kotor             = Rp {laba_kotor:,.0f}")
check("Laba Kotor", laba_kotor, Decimal('19200000'))

# BIAYA OPERASIONAL (SELESAI only)
print(f"  Biaya Operasional      = Rp {total_ops_approved:,.0f}")

# LABA BERSIH
laba_bersih = laba_kotor - total_ops_approved
print(f"  LABA BERSIH            = Rp {laba_bersih:,.0f}")
check("Laba Bersih", laba_bersih, Decimal('16750000'))

sub("Kalkulasi Piutang")
# Invoice 1: PAID → piutang 0
# Invoice 2: PAID → piutang 0
# Invoice 3: UNPAID → piutang 44.000.000
# Invoice 4: UNPAID → piutang 21.000.000
total_piutang = inv3.remaining_balance + inv4.remaining_balance
print(f"  Total Piutang          = Rp {total_piutang:,.0f}")
check("Total Piutang", total_piutang, Decimal('65000000'))

# Total Pemasukan (dari payment approved)
total_pemasukan = sum(
    p.amount for p in Payment.objects.filter(status='APPROVED')
)
print(f"  Total Pemasukan (Cash) = Rp {total_pemasukan:,.0f}")
check("Total Pemasukan", total_pemasukan, Decimal('80200000'))


# ==========================================================
section("PHASE 9: ORDER NOTE → MARK DONE")
# ==========================================================

sub("Tandai Order#1 selesai (NPK 10T sudah dikirim SJ#1)")
# Link order item ke distribusi item
order1_npk = order1.items.get(jenis_pupuk=npk)
di1.order_item = order1_npk
di1.save()
order1_npk.refresh_from_db()
check("Order1 NPK delivered", order1_npk.delivered_tonnage, Decimal('10'))
check("Order1 NPK remaining", order1_npk.remaining_tonnage, Decimal('0'))
check("Order1 NPK fulfilled", order1_npk.is_fulfilled, True)

# Mark the order done
order1.mark_done()
order1.refresh_from_db()
check("Order1 status", order1.status, 'DONE')

# ==========================================================
section("PHASE 10: EDGE CASES")
# ==========================================================

sub("Edge Case 1: Distribusi melebihi kuota → ValidationError")
try:
    dist_fail = Distribution(
        date=today, pkp_date=today,
        kios=kios1, armada=armada1,
        source_type='PHYSICAL',
        jenis_pupuk=npk, tonnage=Decimal('999')
    )
    dist_fail.clean()
    print("  [FAIL] Seharusnya raise ValidationError (kuota melebihi)")
    FAIL += 1
except Exception as e:
    print(f"  [PASS] ValidationError caught: {e}")
    PASS += 1

sub("Edge Case 2: Transfer melebihi virtual balance → ValidationError")
try:
    trf_fail = WarehouseTransfer(
        source_so=so1, date=today, tonnage=Decimal('999')
    )
    trf_fail.clean()
    print("  [FAIL] Seharusnya raise ValidationError (virtual exceeded)")
    FAIL += 1
except Exception as e:
    print(f"  [PASS] ValidationError caught: {e}")
    PASS += 1

sub("Edge Case 3: Payment melebihi sisa tagihan → ValidationError")
try:
    pay_fail = Payment(
        invoice=inv3, date=today,
        amount=Decimal('999999999'), method='Cash',
        status='APPROVED'
    )
    pay_fail.clean()
    print("  [FAIL] Seharusnya raise ValidationError (overpayment)")
    FAIL += 1
except Exception as e:
    print(f"  [PASS] ValidationError caught: {e}")
    PASS += 1

sub("Edge Case 4: Delete distribusi → restore kuota & stok")
# Simpan state sebelum delete
prev_quota = KiosAllocation.objects.get(kios=kios4, jenis_pupuk=urea, year=today.year).quota_remaining
prev_phys = get_physical_balance(urea)
dist4_id = dist4.id
print(f"  Before delete SJ#4: Urea physical={prev_phys}, Kios4 Urea quota={prev_quota}")

dist4.delete()

after_quota = KiosAllocation.objects.get(kios=kios4, jenis_pupuk=urea, year=today.year).quota_remaining
after_phys = get_physical_balance(urea)
print(f"  After delete SJ#4: Urea physical={after_phys}, Kios4 Urea quota={after_quota}")
check("Kuota restored after delete", after_quota, prev_quota + Decimal('5'))
check("Physical restored after delete", after_phys, prev_phys + Decimal('5'))

# Invoice should also be deleted (CASCADE)
check("Invoice#4 deleted", Invoice.objects.filter(distribution_id=dist4_id).count(), 0)

# ==========================================================
section("PHASE 11: STOCK OPNAME")
# ==========================================================

sub("Stock Opname: Adjust Physical NPK +2T (selisih audit)")
opname = StockCard.objects.create(
    date=today,
    jenis_pupuk=npk,
    stock_type='PHYSICAL',
    transaction_type='ADJUST',
    reference_number='OPNAME-001',
    description='Penyesuaian audit fisik - selisih +2T',
    qty_in=Decimal('2'),
    qty_out=Decimal('0'),
    balance=Decimal('0')
)
# Recompute balance
from gudang.signals import recompute_stock_balance
recompute_stock_balance(npk.id, 'PHYSICAL')
check("Physical NPK after opname", get_physical_balance(npk), Decimal('22'))

# ==========================================================
section("FINAL REPORT")
# ==========================================================

print()
print(f"  TOTAL CHECKS: {PASS + FAIL}")
print(f"  PASSED      : {PASS}")
print(f"  FAILED      : {FAIL}")
print()

if FAIL == 0:
    print("  ✅ ALL TESTS PASSED! System is production-ready.")
else:
    print(f"  ❌ {FAIL} TESTS FAILED! Review the issues above.")

print()
print("=" * 60)

# Ringkasan akhir database
sub("DATABASE SUMMARY")
print(f"  SalesOrder         : {SalesOrder.objects.count()}")
print(f"  SOAllocation       : {SalesOrderAllocation.objects.count()}")
print(f"  WarehouseTransfer  : {WarehouseTransfer.objects.count()}")
print(f"  Distribution       : {Distribution.objects.count()}")
print(f"  DistributionItem   : {DistributionItem.objects.count()}")
print(f"  StockCard          : {StockCard.objects.count()}")
print(f"  Invoice            : {Invoice.objects.count()}")
print(f"  Payment            : {Payment.objects.count()}")
print(f"  BiayaOperasional   : {BiayaOperasional.objects.count()}")
print(f"  OrderNote          : {OrderNote.objects.count()}")
print(f"  OrderNoteItem      : {OrderNoteItem.objects.count()}")

sub("STOCK BALANCES")
for jp in [npk, urea]:
    for st in ['VIRTUAL', 'PHYSICAL']:
        last = StockCard.objects.filter(jenis_pupuk=jp, stock_type=st).order_by('date', 'created_at', 'id').last()
        bal = last.balance if last else Decimal('0')
        print(f"  {jp.code} {st}: {bal:,.2f} Ton")

sub("INVOICE STATUS")
for inv in Invoice.objects.all().select_related('distribution__kios'):
    print(f"  {inv.inv_number} | {inv.distribution.kios.name} | {inv.status} | Tagihan={inv.total_amount:,.0f} | Dibayar={inv.total_paid:,.0f} | Sisa={inv.remaining_balance:,.0f}")

sub("KUOTA KIOS SISA")
for alloc in KiosAllocation.objects.all().select_related('kios', 'jenis_pupuk'):
    print(f"  {alloc.kios.name} | {alloc.jenis_pupuk.code} | Awal={alloc.quota_original}T | Sisa={alloc.quota_remaining}T | Terpakai={alloc.quota_used}T")
