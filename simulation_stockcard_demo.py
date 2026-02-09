"""
SIMULATION: Demo Data untuk Kartu Stok (Versi Baru)
=====================================================
Script ini membuat data lengkap agar user bisa melihat kartu stok
di website dengan deskripsi baru:
  - Transfer: "Ditarik ke Gudang (SO: xxx)" & "Terima dari Pabrik (SO: xxx)"
  - Distribusi VIRTUAL: "Distribusi ke {kios} (SO: xxx)" & "Terima dari Pabrik (SO: xxx)"
  - Distribusi PHYSICAL: "Distribusi ke {kios}"

Skenario:
  1. SO NPK 30T → Transfer 15T ke Gudang → Distribusi 10T (PHYSICAL) ke Kios A
  2. SO UREA 20T → Distribusi 8T (VIRTUAL) langsung ke Kios B
  3. SO NPK (sama) → Distribusi 5T (VIRTUAL) langsung ke Kios A
  4. SO UREA → Transfer 10T ke Gudang → Distribusi 5T (PHYSICAL) ke Kios A

Jalankan:
  python manage.py flush --no-input
  python simulation_stockcard_demo.py

Lalu buka website → login admin/admin123 → Kartu Stok
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sim_dp.settings')
django.setup()

from django.contrib.auth.models import User, Group
from core.models import (
    CompanyProfile, Kabupaten, Kecamatan, JenisPupuk,
    FertilizerPrice, Kios, KiosAllocation, Armada,
)
from gudang.models import (
    SalesOrder, SalesOrderAllocation, WarehouseTransfer,
    Distribution, DistributionItem, StockCard,
)
from keuangan.models import Invoice, Payment
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction

# ═══════════════════════════════════════
# HELPER
# ═══════════════════════════════════════
today = date.today()
year = today.year

def ok(msg):
    print(f"  \033[92m[OK]\033[0m {msg}")

def info(msg):
    print(f"  \033[94m[i]\033[0m {msg}")

def header(title):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)

# ═══════════════════════════════════════
header("PHASE 1: MASTER DATA")
# ═══════════════════════════════════════

# Superuser
admin = User.objects.create_superuser('admin', 'admin@demo.com', 'admin123')
grp_owner, _ = Group.objects.get_or_create(name='Owner')
admin.groups.add(grp_owner)
ok("Superuser: admin / admin123 (group: Owner)")

# Company Profile
company = CompanyProfile.objects.create(
    name='CV. BERKAH TANI NUSANTARA',
    address='Jl. Raya Salatiga - Semarang KM 5, Kab. Semarang',
    phone='0812-3456-7890',
    email='info@berkahtani.co.id',
    bank_name='Bank BCA',
    bank_account='1234567890',
    bank_account_name='CV Berkah Tani Nusantara',
)
ok(f"Company: {company.name}")

# Wilayah
kab = Kabupaten.objects.create(name='Kab. Semarang', is_active=True)
kec_a = Kecamatan.objects.create(name='Ungaran Barat', kabupaten=kab)
kec_b = Kecamatan.objects.create(name='Ambarawa', kabupaten=kab)
ok(f"Kabupaten: {kab.name} → Kecamatan: {kec_a.name}, {kec_b.name}")

# Jenis Pupuk
npk = JenisPupuk.objects.create(name='NPK Phonska', code='NPK', is_active=True)
urea = JenisPupuk.objects.create(name='Urea', code='UREA', is_active=True)
ok(f"Jenis Pupuk: {npk.name}, {urea.name}")

# Harga per Ton
NPK_SELL, NPK_BUY = Decimal('5500000'), Decimal('4800000')
UREA_SELL, UREA_BUY = Decimal('4200000'), Decimal('3600000')
FertilizerPrice.objects.create(jenis_pupuk=npk, kabupaten=kab, price_sell=NPK_SELL, price_buy=NPK_BUY)
FertilizerPrice.objects.create(jenis_pupuk=urea, kabupaten=kab, price_sell=UREA_SELL, price_buy=UREA_BUY)
ok(f"Harga NPK: Jual={NPK_SELL:,.0f}/T, Beli={NPK_BUY:,.0f}/T")
ok(f"Harga UREA: Jual={UREA_SELL:,.0f}/T, Beli={UREA_BUY:,.0f}/T")

# Kios
kios_a = Kios.objects.create(
    name='Kios Tani Makmur', pic_name='Pak Budi',
    kecamatan=kec_a, address='Jl. Ungaran No.10', phone='0812-1111-0001',
    is_active=True,
)
kios_b = Kios.objects.create(
    name='Kios Subur Jaya', pic_name='Bu Sari',
    kecamatan=kec_b, address='Jl. Ambarawa No.25', phone='0812-2222-0002',
    is_active=True,
)
ok(f"Kios A: {kios_a.name} ({kec_a.name})")
ok(f"Kios B: {kios_b.name} ({kec_b.name})")

# Alokasi Kuota
for kios in [kios_a, kios_b]:
    for jp, ton in [(npk, Decimal('50')), (urea, Decimal('40'))]:
        KiosAllocation.objects.create(
            kios=kios, jenis_pupuk=jp, year=year,
            quota_original=ton, quota_remaining=ton,
        )
ok("Alokasi kuota: NPK 50T & UREA 40T per kios per tahun")

# Armada
armada = Armada.objects.create(
    plate_number='H-1234-AB', driver_name='Supri',
    vehicle_type='Truk Engkel', is_active=True,
)
ok(f"Armada: {armada.plate_number} ({armada.driver_name})")

# Staff Gudang
staff = Group.objects.get_or_create(name='Staff Gudang')[0]

# ═══════════════════════════════════════
header("PHASE 2: SKENARIO 1 — Transfer NPK + Distribusi PHYSICAL")
# ═══════════════════════════════════════
info("SO NPK 30T → Transfer 15T → Distribusi 10T (PHYSICAL) ke Kios Tani Makmur")

so_npk = SalesOrder.objects.create(so_number='SO-2026-NPK-001', date=today - timedelta(days=7), jenis_pupuk=npk)
SalesOrderAllocation.objects.create(sales_order=so_npk, kecamatan=kec_a, tonnage=Decimal('30'))
ok(f"SO: {so_npk.so_number} | 30 Ton NPK")

# Transfer 15T ke gudang
wt1 = WarehouseTransfer.objects.create(
    source_so=so_npk, date=today - timedelta(days=6),
    tonnage=Decimal('15'), reference_code='SJ-PABRIK-001',
)
ok(f"Transfer 15T NPK → Gudang | Kartu: 'Ditarik ke Gudang (SO: {so_npk.so_number})'")
ok(f"                          | Kartu: 'Terima dari Pabrik (SO: {so_npk.so_number})'")

# Distribusi 10T PHYSICAL ke Kios A
with transaction.atomic():
    dist1 = Distribution(
        date=today - timedelta(days=5), pkp_date=today - timedelta(days=5),
        kios=kios_a, armada=armada,
        source_type='PHYSICAL', jenis_pupuk=npk, tonnage=Decimal('10'),
    )
    dist1.save()
    item1 = DistributionItem.objects.create(
        distribution=dist1, jenis_pupuk=npk,
        source_type='PHYSICAL', tonnage=Decimal('10'),
    )
ok(f"Distribusi 10T NPK (PHYSICAL) → {kios_a.name}")
ok(f"  Kartu: 'Distribusi ke {kios_a.name}' (Physical OUT)")

# ═══════════════════════════════════════
header("PHASE 3: SKENARIO 2 — Distribusi UREA VIRTUAL langsung ke Kios B")
# ═══════════════════════════════════════
info("SO UREA 20T → Distribusi 8T (VIRTUAL) langsung ke Kios Subur Jaya")

so_urea = SalesOrder.objects.create(so_number='SO-2026-UREA-001', date=today - timedelta(days=4), jenis_pupuk=urea)
SalesOrderAllocation.objects.create(sales_order=so_urea, kecamatan=kec_b, tonnage=Decimal('20'))
ok(f"SO: {so_urea.so_number} | 20 Ton UREA")

with transaction.atomic():
    dist2 = Distribution(
        date=today - timedelta(days=3), pkp_date=today - timedelta(days=3),
        kios=kios_b, armada=armada,
        source_type='VIRTUAL', source_so=so_urea,
        jenis_pupuk=urea, tonnage=Decimal('8'),
    )
    dist2.save()
    item2 = DistributionItem.objects.create(
        distribution=dist2, jenis_pupuk=urea,
        source_type='VIRTUAL', source_so=so_urea, tonnage=Decimal('8'),
    )
ok(f"Distribusi 8T UREA (VIRTUAL) → {kios_b.name}")
ok(f"  Kartu Virtual: 'Distribusi ke {kios_b.name} (SO: {so_urea.so_number})'")
ok(f"  Kartu Fisik IN: 'Terima dari Pabrik (SO: {so_urea.so_number})'")
ok(f"  Kartu Fisik OUT: 'Distribusi ke {kios_b.name}'")

# ═══════════════════════════════════════
header("PHASE 4: SKENARIO 3 — Distribusi NPK VIRTUAL langsung ke Kios A")
# ═══════════════════════════════════════
info("SO NPK (sama) → Distribusi 5T (VIRTUAL) langsung ke Kios Tani Makmur")

with transaction.atomic():
    dist3 = Distribution(
        date=today - timedelta(days=2), pkp_date=today - timedelta(days=2),
        kios=kios_a, armada=armada,
        source_type='VIRTUAL', source_so=so_npk,
        jenis_pupuk=npk, tonnage=Decimal('5'),
    )
    dist3.save()
    item3 = DistributionItem.objects.create(
        distribution=dist3, jenis_pupuk=npk,
        source_type='VIRTUAL', source_so=so_npk, tonnage=Decimal('5'),
    )
ok(f"Distribusi 5T NPK (VIRTUAL) → {kios_a.name}")
ok(f"  Kartu Virtual: 'Distribusi ke {kios_a.name} (SO: {so_npk.so_number})'")
ok(f"  Kartu Fisik IN: 'Terima dari Pabrik (SO: {so_npk.so_number})'")
ok(f"  Kartu Fisik OUT: 'Distribusi ke {kios_a.name}'")

# ═══════════════════════════════════════
header("PHASE 5: SKENARIO 4 — Transfer UREA + Distribusi PHYSICAL")
# ═══════════════════════════════════════
info("SO UREA (sama) → Transfer 10T → Distribusi 5T (PHYSICAL) ke Kios Tani Makmur")

wt2 = WarehouseTransfer.objects.create(
    source_so=so_urea, date=today - timedelta(days=1),
    tonnage=Decimal('10'), reference_code='SJ-PABRIK-002',
)
ok(f"Transfer 10T UREA → Gudang | SO: {so_urea.so_number}")

with transaction.atomic():
    dist4 = Distribution(
        date=today, pkp_date=today,
        kios=kios_a, armada=armada,
        source_type='PHYSICAL', jenis_pupuk=urea, tonnage=Decimal('5'),
    )
    dist4.save()
    item4 = DistributionItem.objects.create(
        distribution=dist4, jenis_pupuk=urea,
        source_type='PHYSICAL', tonnage=Decimal('5'),
    )
ok(f"Distribusi 5T UREA (PHYSICAL) → {kios_a.name}")
ok(f"  Kartu: 'Distribusi ke {kios_a.name}' (Physical OUT)")

# ═══════════════════════════════════════
header("PHASE 6: VERIFIKASI KARTU STOK")
# ═══════════════════════════════════════

all_cards = StockCard.objects.select_related('jenis_pupuk').order_by('stock_type', 'date', 'created_at')

print()
print(f"  {'TIPE':<10} {'TGL':<12} {'PUPUK':<12} {'KETERANGAN':<50} {'IN':>8} {'OUT':>8} {'SALDO':>8}")
print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*50} {'-'*8} {'-'*8} {'-'*8}")

for c in all_cards:
    print(
        f"  {c.stock_type:<10} "
        f"{c.date.strftime('%d/%m/%Y'):<12} "
        f"{c.jenis_pupuk.code:<12} "
        f"{c.description:<50} "
        f"{c.qty_in:>8.2f} "
        f"{c.qty_out:>8.2f} "
        f"{c.balance:>8.2f}"
    )

# Validasi deskripsi
errors = 0

def validate(card_ref, expected_desc):
    global errors
    try:
        card = StockCard.objects.get(reference_number=card_ref)
        if card.description != expected_desc:
            errors += 1
            print(f"  \033[91m[FAIL]\033[0m {card_ref}: '{card.description}' != '{expected_desc}'")
        else:
            print(f"  \033[92m[PASS]\033[0m {card_ref}: {card.description}")
    except StockCard.DoesNotExist:
        errors += 1
        print(f"  \033[91m[FAIL]\033[0m {card_ref}: Card NOT FOUND")

print()
print("--- Validasi Deskripsi Kartu Stok ---")

# Transfer NPK (wt1)
validate(f"TRF-{wt1.id}-V", f"Ditarik ke Gudang (SO: {so_npk.so_number})")
validate(f"TRF-{wt1.id}-P", f"Terima dari Pabrik (SO: {so_npk.so_number})")

# Distribusi 1 (PHYSICAL NPK)
validate(f"SJ-{dist1.id}-{item1.id}-P-OUT", f"Distribusi ke {kios_a.name}")

# Distribusi 2 (VIRTUAL UREA)
validate(f"SJ-{dist2.id}-{item2.id}-V", f"Distribusi ke {kios_b.name} (SO: {so_urea.so_number})")
validate(f"SJ-{dist2.id}-{item2.id}-P-IN", f"Terima dari Pabrik (SO: {so_urea.so_number})")
validate(f"SJ-{dist2.id}-{item2.id}-P-OUT", f"Distribusi ke {kios_b.name}")

# Distribusi 3 (VIRTUAL NPK)
validate(f"SJ-{dist3.id}-{item3.id}-V", f"Distribusi ke {kios_a.name} (SO: {so_npk.so_number})")
validate(f"SJ-{dist3.id}-{item3.id}-P-IN", f"Terima dari Pabrik (SO: {so_npk.so_number})")
validate(f"SJ-{dist3.id}-{item3.id}-P-OUT", f"Distribusi ke {kios_a.name}")

# Transfer UREA (wt2)
validate(f"TRF-{wt2.id}-V", f"Ditarik ke Gudang (SO: {so_urea.so_number})")
validate(f"TRF-{wt2.id}-P", f"Terima dari Pabrik (SO: {so_urea.so_number})")

# Distribusi 4 (PHYSICAL UREA)
validate(f"SJ-{dist4.id}-{item4.id}-P-OUT", f"Distribusi ke {kios_a.name}")

# Verifikasi Saldo
print()
print("--- Validasi Saldo ---")

def check_balance(jp, stype, expected):
    global errors
    from django.db.models.functions import Coalesce
    from django.db.models import Sum
    agg = StockCard.objects.filter(jenis_pupuk=jp, stock_type=stype).aggregate(
        i=Coalesce(Sum('qty_in'), Decimal('0')),
        o=Coalesce(Sum('qty_out'), Decimal('0')),
    )
    actual = agg['i'] - agg['o']
    if abs(actual - expected) > Decimal('0.01'):
        errors += 1
        print(f"  \033[91m[FAIL]\033[0m {jp.code} {stype}: {actual} (expected {expected})")
    else:
        print(f"  \033[92m[PASS]\033[0m {jp.code} {stype}: {actual}")

# NPK Virtual: 30(SO allocation) was tracked via signals already
# Virtual: OUT_TRF 15 + OUT_DIST_V 5 = 20 out. No virtual IN from signals.
# -> net = 0 - 20 = -20 (virtual balance is tracked via SO, StockCard only has OUT)
# Actually IN_SO is only created by allocation signal... let me check.

# Let me just verify Physical balance which is more straightforward:
# NPK Physical: IN_TRF 15 + IN_DIST_P 5 = 20 in | OUT_DIST_P 10 + 5 = 15 out → net = 5
check_balance(npk, 'PHYSICAL', Decimal('5'))

# UREA Physical: IN_DIST_P 8 + IN_TRF 10 = 18 in | OUT_DIST_P 8 + 5 = 13 out → net = 5
check_balance(urea, 'PHYSICAL', Decimal('5'))

# NPK Virtual: IN_SO 30 - OUT_TRF 15 - OUT_DIST_V 5 = 10
check_balance(npk, 'VIRTUAL', Decimal('10'))

# UREA Virtual: IN_SO 20 - OUT_TRF 10 - OUT_DIST_V 8 = 2
check_balance(urea, 'VIRTUAL', Decimal('2'))

# Verifikasi Invoice
print()
print("--- Verifikasi Invoice ---")
inv_count = Invoice.objects.count()
print(f"  \033[92m[OK]\033[0m Total Invoice: {inv_count}")
for inv in Invoice.objects.select_related('distribution__kios').all():
    print(f"       {inv.inv_number} → {inv.distribution.kios.name} | "
          f"Rp {inv.total_amount:,.0f} | Status: {inv.status}")

# ═══════════════════════════════════════
header("HASIL AKHIR")
# ═══════════════════════════════════════
total_cards = StockCard.objects.count()
print()
print(f"  Total Kartu Stok: {total_cards}")
print(f"  Total Invoice   : {inv_count}")
print(f"  Error           : {errors}")
print()
if errors == 0:
    print("  \033[92m✓ SEMUA VALIDASI LULUS!\033[0m")
    print()
    print("  Silakan buka website dan login:")
    print("    Username: admin")
    print("    Password: admin123")
    print()
    print("  Lalu navigasi ke:")
    print("    → Kartu Stok (menu Gudang)")
    print("    → Pilih tab VIRTUAL atau FISIK untuk melihat deskripsi baru")
    print("    → Export PDF untuk melihat kolom 'Keterangan'")
else:
    print(f"  \033[91m✗ {errors} VALIDASI GAGAL!\033[0m")
print()
sys.exit(0 if errors == 0 else 1)
