"""
SIMULATION E2E: 1x NPK + 1x UREA → Verifikasi Laporan Keuangan
=================================================================
Script ini:
1. Setup master data (company, kabupaten, kecamatan, jenis pupuk, harga, kios, armada)
2. Buat 1 transaksi NPK end-to-end (SO → Transfer → Distribusi → Invoice → Payment)
3. Buat 1 transaksi UREA end-to-end
4. Verifikasi laporan keuangan: omzet, HPP, laba harus tampil di baris yang BENAR

Jalankan: python manage.py flush --no-input && python simulation_e2e_verify.py
"""
import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sim_dp.settings')
django.setup()

from django.contrib.auth.models import User, Group
from core.models import (
    CompanyProfile, Kabupaten, Kecamatan, JenisPupuk,
    FertilizerPrice, Kios, KiosAllocation, Armada, UserProfile
)
from gudang.models import (
    SalesOrder, SalesOrderAllocation, WarehouseTransfer,
    Distribution, DistributionItem, StockCard,
    OrderNote, OrderNoteItem
)
from keuangan.models import BiayaOperasional, Invoice, Payment
from core.utils import get_price_for
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.db import transaction

# ==========================================
# HELPER
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
        print(f"  [\033[91m{status}\033[0m] {label}: Got {actual}, Expected {expected}")
    else:
        PASS += 1
        print(f"  [\033[92m{status}\033[0m] {label}: {actual}")
    return ok

def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)

def sub(title):
    print(f"\n--- {title} ---")

today = date.today()
current_year = today.year

# ══════════════════════════════════════════════════════════════
section("PHASE 1: SETUP MASTER DATA")
# ══════════════════════════════════════════════════════════════

admin = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
print(f"[OK] Superuser: admin / admin123")

grp_owner, _ = Group.objects.get_or_create(name='Owner')
grp_staff, _ = Group.objects.get_or_create(name='Staff Gudang')

company = CompanyProfile.objects.create(
    name='PT PUPUK NUSANTARA',
    address='Jl. Raya Semarang KM 12',
    phone='024-6921234',
    email='info@pupuk.co.id',
    bank_name='BCA',
    bank_account='1234567890',
    bank_account_name='PT Pupuk Nusantara',
)
print(f"[OK] Company: {company.name}")

kab = Kabupaten.objects.create(name='Semarang', is_active=True)
kec = Kecamatan.objects.create(name='Ungaran', kabupaten=kab)
print(f"[OK] Kabupaten: {kab.name} → Kecamatan: {kec.name}")

npk = JenisPupuk.objects.create(name='NPK Phonska', code='NPK', is_active=True)
urea = JenisPupuk.objects.create(name='Urea', code='UREA', is_active=True)
organik = JenisPupuk.objects.create(name='Organik', code='ORGANIK', is_active=True)
za = JenisPupuk.objects.create(name='ZA', code='ZA', is_active=True)
print(f"[OK] Jenis Pupuk: NPK, UREA, ORGANIK, ZA")

# Harga per ton
NPK_SELL = Decimal('5500000')
NPK_BUY  = Decimal('4800000')
UREA_SELL = Decimal('4200000')
UREA_BUY  = Decimal('3600000')
ORGANIK_SELL = Decimal('3000000')
ORGANIK_BUY  = Decimal('2500000')
ZA_SELL = Decimal('3500000')
ZA_BUY  = Decimal('3000000')

FertilizerPrice.objects.create(jenis_pupuk=npk, kabupaten=kab, price_sell=NPK_SELL, price_buy=NPK_BUY)
FertilizerPrice.objects.create(jenis_pupuk=urea, kabupaten=kab, price_sell=UREA_SELL, price_buy=UREA_BUY)
FertilizerPrice.objects.create(jenis_pupuk=organik, kabupaten=kab, price_sell=ORGANIK_SELL, price_buy=ORGANIK_BUY)
FertilizerPrice.objects.create(jenis_pupuk=za, kabupaten=kab, price_sell=ZA_SELL, price_buy=ZA_BUY)
print(f"[OK] Harga: NPK={NPK_SELL:,.0f}/{NPK_BUY:,.0f} | UREA={UREA_SELL:,.0f}/{UREA_BUY:,.0f}")
print(f"           ORGANIK={ORGANIK_SELL:,.0f}/{ORGANIK_BUY:,.0f} | ZA={ZA_SELL:,.0f}/{ZA_BUY:,.0f}")

kios = Kios.objects.create(
    name='Kios Tani Sejahtera', address='Jl. Ungaran Raya No.45',
    pic_name='Pak Budi', phone='0812-1111-0001',
    kecamatan=kec, is_active=True
)
for jp, ton in [(npk, 50), (urea, 30), (organik, 20), (za, 20)]:
    KiosAllocation.objects.create(
        kios=kios, jenis_pupuk=jp, year=current_year,
        quota_original=Decimal(str(ton)), quota_remaining=Decimal(str(ton))
    )
print(f"[OK] Kios: {kios.name} | Alokasi: NPK=50T, UREA=30T, ORGANIK=20T, ZA=20T")

armada = Armada.objects.create(
    plate_number='H-1234-AB', driver_name='Supri',
    vehicle_type='Truk Engkel', is_active=True
)
print(f"[OK] Armada: {armada.plate_number} ({armada.driver_name})")

# ══════════════════════════════════════════════════════════════
section("PHASE 2: TRANSAKSI NPK (End-to-End)")
# ══════════════════════════════════════════════════════════════

NPK_TON = Decimal('10')

sub("2a. Buat SO NPK 20 Ton")
so_npk = SalesOrder.objects.create(so_number='SO-NPK-001', date=today, jenis_pupuk=npk)
SalesOrderAllocation.objects.create(sales_order=so_npk, kecamatan=kec, tonnage=Decimal('20'))
so_npk.refresh_from_db()
check("SO NPK virtual balance", so_npk.get_virtual_balance(), Decimal('20'))

sub(f"2b. Transfer NPK {NPK_TON}T ke Gudang")
wt_npk = WarehouseTransfer.objects.create(source_so=so_npk, date=today, tonnage=NPK_TON, reference_code='SJ-NPK-001')
so_npk.refresh_from_db()
check("SO NPK virtual after transfer", so_npk.get_virtual_balance(), Decimal('10'))

sub(f"2c. Distribusi NPK {NPK_TON}T ke {kios.name}")
with transaction.atomic():
    dist_npk = Distribution(
        date=today, pkp_date=today,
        kios=kios, armada=armada,
        source_type='PHYSICAL', jenis_pupuk=npk,
        tonnage=NPK_TON
    )
    dist_npk.save()
    item_npk = DistributionItem.objects.create(
        distribution=dist_npk,
        jenis_pupuk=npk,
        source_type='PHYSICAL',
        tonnage=NPK_TON
    )

# Verifikasi price snapshot ter-lock
item_npk.refresh_from_db()
check("NPK price_sell_snapshot", item_npk.price_sell_snapshot, NPK_SELL)
check("NPK price_buy_snapshot", item_npk.price_buy_snapshot, NPK_BUY)

sub("2d. Verifikasi Invoice NPK")
dist_npk.refresh_from_db()
try:
    inv_npk = Invoice.objects.get(distribution=dist_npk)
    expected_inv_npk = NPK_TON * NPK_SELL
    check("Invoice NPK total_amount", inv_npk.total_amount, expected_inv_npk)
    check("Invoice NPK status", inv_npk.status, 'UNPAID')
    print(f"  [INFO] Invoice: {inv_npk.inv_number} → Rp {inv_npk.total_amount:,.0f}")
except Invoice.DoesNotExist:
    check("Invoice NPK exists", False, True)

sub("2e. Bayar Full NPK")
pay_npk = Payment.objects.create(
    invoice=inv_npk, date=today,
    amount=expected_inv_npk, method='Transfer BCA', status='APPROVED'
)
inv_npk.refresh_from_db()
check("Invoice NPK status after full pay", inv_npk.status, 'PAID')
check("Invoice NPK remaining", inv_npk.remaining_balance, Decimal('0'))

# ══════════════════════════════════════════════════════════════
section("PHASE 3: TRANSAKSI UREA (End-to-End)")
# ══════════════════════════════════════════════════════════════

UREA_TON = Decimal('5')

sub("3a. Buat SO UREA 15 Ton")
so_urea = SalesOrder.objects.create(so_number='SO-UREA-001', date=today, jenis_pupuk=urea)
SalesOrderAllocation.objects.create(sales_order=so_urea, kecamatan=kec, tonnage=Decimal('15'))
so_urea.refresh_from_db()
check("SO UREA virtual balance", so_urea.get_virtual_balance(), Decimal('15'))

sub(f"3b. Distribusi UREA {UREA_TON}T langsung dari Pabrik (VIRTUAL)")
with transaction.atomic():
    dist_urea = Distribution(
        date=today, pkp_date=today,
        kios=kios, armada=armada,
        source_type='VIRTUAL', source_so=so_urea,
        jenis_pupuk=urea, tonnage=UREA_TON
    )
    dist_urea.save()
    item_urea = DistributionItem.objects.create(
        distribution=dist_urea,
        jenis_pupuk=urea,
        source_type='VIRTUAL',
        source_so=so_urea,
        tonnage=UREA_TON
    )

item_urea.refresh_from_db()
check("UREA price_sell_snapshot", item_urea.price_sell_snapshot, UREA_SELL)
check("UREA price_buy_snapshot", item_urea.price_buy_snapshot, UREA_BUY)

sub("3c. Verifikasi Invoice UREA")
try:
    inv_urea = Invoice.objects.get(distribution=dist_urea)
    expected_inv_urea = UREA_TON * UREA_SELL
    check("Invoice UREA total_amount", inv_urea.total_amount, expected_inv_urea)
    check("Invoice UREA status", inv_urea.status, 'UNPAID')
    print(f"  [INFO] Invoice: {inv_urea.inv_number} → Rp {inv_urea.total_amount:,.0f}")
except Invoice.DoesNotExist:
    check("Invoice UREA exists", False, True)

sub("3d. Bayar Cicilan UREA (setengah)")
half_urea = expected_inv_urea / 2
pay_urea_1 = Payment.objects.create(
    invoice=inv_urea, date=today,
    amount=half_urea, method='Transfer BCA', status='APPROVED'
)
inv_urea.refresh_from_db()
check("Invoice UREA status after partial", inv_urea.status, 'PARTIAL')
check("Invoice UREA remaining", inv_urea.remaining_balance, half_urea)

sub("3e. Bayar Sisa UREA")
pay_urea_2 = Payment.objects.create(
    invoice=inv_urea, date=today,
    amount=half_urea, method='Tunai', status='APPROVED'
)
inv_urea.refresh_from_db()
check("Invoice UREA status after full", inv_urea.status, 'PAID')
check("Invoice UREA remaining", inv_urea.remaining_balance, Decimal('0'))

# ══════════════════════════════════════════════════════════════
section("PHASE 4: VERIFIKASI LAPORAN KEUANGAN")
# ══════════════════════════════════════════════════════════════

sub("4a. Verifikasi DistributionItem.jenis_pupuk")
all_items = DistributionItem.objects.select_related('jenis_pupuk').all()
for item in all_items:
    print(f"  [INFO] Item: {item.jenis_pupuk.code} | "
          f"Tonnage={item.tonnage}T | "
          f"sell_snap={item.price_sell_snapshot} | "
          f"buy_snap={item.price_buy_snapshot}")

sub("4b. Hitung Omzet & HPP per Jenis (logika laporan keuangan)")
start_date = today.replace(day=1)
end_date = today

dist_qs = DistributionItem.objects.select_related(
    'distribution__kios__kecamatan__kabupaten', 'jenis_pupuk'
).filter(
    distribution__date__range=[start_date, end_date],
    distribution__kios__kecamatan__kabupaten=kab
)

active_types = JenisPupuk.objects.filter(is_active=True).order_by('name')
prices = {}
for jp in active_types:
    prices[jp.id] = get_price_for(jp, kab)

print(f"\n  {'JENIS':<15} {'QTY':>6} {'OMZET':>18} {'HPP':>18} {'LABA KOTOR':>18}")
print(f"  {'-'*15} {'-'*6} {'-'*18} {'-'*18} {'-'*18}")

total_omzet_calc = Decimal('0')
total_modal_calc = Decimal('0')

for jp in active_types:
    price = prices[jp.id]
    items = dist_qs.filter(jenis_pupuk=jp)
    qty = Decimal('0')
    omzet = Decimal('0')
    modal = Decimal('0')
    for item in items:
        ton = item.tonnage or Decimal('0')
        sell = item.price_sell_snapshot if item.price_sell_snapshot is not None else price.price_sell
        buy = item.price_buy_snapshot if item.price_buy_snapshot is not None else price.price_buy
        qty += ton
        omzet += ton * sell
        modal += ton * buy
    gp = omzet - modal
    total_omzet_calc += omzet
    total_modal_calc += modal
    print(f"  {jp.name:<15} {qty:>6} {omzet:>18,.0f} {modal:>18,.0f} {gp:>18,.0f}")

print(f"  {'TOTAL':<15} {'':>6} {total_omzet_calc:>18,.0f} {total_modal_calc:>18,.0f} {total_omzet_calc - total_modal_calc:>18,.0f}")

sub("4c. Validasi Angka Laporan")

# NPK: 10T × 5.5jt = 55jt omzet | 10T × 4.8jt = 48jt HPP
expected_npk_omzet = NPK_TON * NPK_SELL
expected_npk_hpp = NPK_TON * NPK_BUY
# UREA: 5T × 4.2jt = 21jt omzet | 5T × 3.6jt = 18jt HPP
expected_urea_omzet = UREA_TON * UREA_SELL
expected_urea_hpp = UREA_TON * UREA_BUY

# Hitung aktual dari item
npk_items = dist_qs.filter(jenis_pupuk=npk)
urea_items = dist_qs.filter(jenis_pupuk=urea)
organik_items = dist_qs.filter(jenis_pupuk=organik)
za_items = dist_qs.filter(jenis_pupuk=za)

# NPK Omzet
npk_omzet_actual = sum(
    (i.tonnage or 0) * (i.price_sell_snapshot if i.price_sell_snapshot is not None else prices[npk.id].price_sell)
    for i in npk_items
)
npk_hpp_actual = sum(
    (i.tonnage or 0) * (i.price_buy_snapshot if i.price_buy_snapshot is not None else prices[npk.id].price_buy)
    for i in npk_items
)
urea_omzet_actual = sum(
    (i.tonnage or 0) * (i.price_sell_snapshot if i.price_sell_snapshot is not None else prices[urea.id].price_sell)
    for i in urea_items
)
urea_hpp_actual = sum(
    (i.tonnage or 0) * (i.price_buy_snapshot if i.price_buy_snapshot is not None else prices[urea.id].price_buy)
    for i in urea_items
)

check("NPK Omzet", Decimal(str(npk_omzet_actual)), expected_npk_omzet)
check("NPK HPP", Decimal(str(npk_hpp_actual)), expected_npk_hpp)
check("NPK Laba Kotor", Decimal(str(npk_omzet_actual - npk_hpp_actual)), expected_npk_omzet - expected_npk_hpp)

check("UREA Omzet", Decimal(str(urea_omzet_actual)), expected_urea_omzet)
check("UREA HPP", Decimal(str(urea_hpp_actual)), expected_urea_hpp)
check("UREA Laba Kotor", Decimal(str(urea_omzet_actual - urea_hpp_actual)), expected_urea_omzet - expected_urea_hpp)

# ORGANIK & ZA harus 0
check("ORGANIK Omzet (harus 0)", Decimal(str(sum((i.tonnage or 0) for i in organik_items))), Decimal('0'))
check("ZA Omzet (harus 0)", Decimal(str(sum((i.tonnage or 0) for i in za_items))), Decimal('0'))

# Total
expected_total_omzet = expected_npk_omzet + expected_urea_omzet
expected_total_hpp = expected_npk_hpp + expected_urea_hpp
check("Total Omzet", total_omzet_calc, expected_total_omzet)
check("Total HPP", total_modal_calc, expected_total_hpp)
check("Total Laba Kotor", total_omzet_calc - total_modal_calc, expected_total_omzet - expected_total_hpp)

sub("4d. Verifikasi Invoice & Payment")
total_invoices = Invoice.objects.count()
total_payments = Payment.objects.filter(status='APPROVED').count()
total_inv_amount = Invoice.objects.aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
total_paid = Payment.objects.filter(status='APPROVED').aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']

check("Jumlah Invoice", total_invoices, 2)
check("Jumlah Payment APPROVED", total_payments, 3)
check("Total Invoice Amount", total_inv_amount, expected_total_omzet)
check("Total Paid", total_paid, expected_total_omzet)
check("Semua Invoice PAID", Invoice.objects.filter(status='PAID').count(), 2)

sub("4e. Verifikasi Kuota Kios")
alloc_npk = KiosAllocation.objects.get(kios=kios, jenis_pupuk=npk, year=current_year)
alloc_urea = KiosAllocation.objects.get(kios=kios, jenis_pupuk=urea, year=current_year)
check("Kuota NPK tersisa", alloc_npk.quota_remaining, Decimal('40'))  # 50 - 10
check("Kuota UREA tersisa", alloc_urea.quota_remaining, Decimal('25'))  # 30 - 5

sub("4f. Verifikasi StockCard Ledger")
phys_npk = StockCard.objects.filter(jenis_pupuk=npk, stock_type='PHYSICAL').aggregate(
    i=Coalesce(Sum('qty_in'), Decimal('0')), o=Coalesce(Sum('qty_out'), Decimal('0'))
)
virt_urea = StockCard.objects.filter(jenis_pupuk=urea, stock_type='VIRTUAL').aggregate(
    i=Coalesce(Sum('qty_in'), Decimal('0')), o=Coalesce(Sum('qty_out'), Decimal('0'))
)
check("NPK Physical net", phys_npk['i'] - phys_npk['o'], Decimal('0'))  # 10 in - 10 out
check("UREA Virtual out", virt_urea['o'], UREA_TON)

# ══════════════════════════════════════════════════════════════
section("HASIL AKHIR")
# ══════════════════════════════════════════════════════════════
print()
total = PASS + FAIL
print(f"  Total Tests : {total}")
print(f"  PASSED      : {PASS}")
print(f"  FAILED      : {FAIL}")
print()
if FAIL == 0:
    print("  \033[92m✓ SEMUA TEST LULUS! Laporan keuangan akurat.\033[0m")
    print("  → NPK muncul di baris NPK")
    print("  → UREA muncul di baris UREA")
    print("  → ORGANIK & ZA tetap Rp 0")
    print("  → Price snapshot terkunci dengan benar")
    print("  → Invoice & payment sesuai")
else:
    print(f"  \033[91m✗ {FAIL} TEST GAGAL! Ada masalah di laporan keuangan.\033[0m")
print()
sys.exit(0 if FAIL == 0 else 1)
