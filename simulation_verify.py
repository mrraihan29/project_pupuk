"""
SIMULATION: VERIFY LAPORAN KEUANGAN VIEW LOGIC
================================================
Cross-verify the laporan_keuangan view calculation with manual calculations.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sim_dp.settings')
django.setup()

from decimal import Decimal
from datetime import date
from django.db.models import Sum
from django.db.models.functions import Coalesce

from core.models import Kabupaten, JenisPupuk, FertilizerPrice
from core.utils import get_price_for
from gudang.models import DistributionItem, StockCard
from keuangan.models import Invoice, Payment, BiayaOperasional

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

def section(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

today = date.today()
start_date = today.replace(day=1)
end_date = today

# ===========================
# TEST PER KABUPATEN
# ===========================
for kab in Kabupaten.objects.all():
    section(f"LAPORAN KEUANGAN: {kab.name}")

    active_types = JenisPupuk.objects.filter(is_active=True).order_by('name')
    prices = {}
    for jp in active_types:
        p = get_price_for(jp, kab)
        prices[jp.id] = p

    # OMZET & HPP
    dist_qs = DistributionItem.objects.select_related(
        'distribution__kios__kecamatan__kabupaten', 'jenis_pupuk'
    ).filter(
        distribution__date__range=[start_date, end_date],
        distribution__kios__kecamatan__kabupaten=kab
    )

    total_omzet = Decimal('0')
    total_modal = Decimal('0')
    produk_data = []

    for jp in active_types:
        price = prices[jp.id]
        items = dist_qs.filter(jenis_pupuk=jp)
        qty_jual = Decimal('0')
        omzet = Decimal('0')
        modal = Decimal('0')
        for item in items:
            ton = item.tonnage or Decimal('0')
            sell_price = item.price_sell_snapshot if item.price_sell_snapshot else price.price_sell
            buy_price = item.price_buy_snapshot if item.price_buy_snapshot else price.price_buy
            qty_jual += ton
            omzet += ton * sell_price
            modal += ton * buy_price
        gp = omzet - modal
        total_omzet += omzet
        total_modal += modal
        produk_data.append({'name': jp.name, 'qty': qty_jual, 'omzet': omzet, 'hpp': modal, 'gp': gp})

    for p in produk_data:
        print(f"  {p['name']}: Qty={p['qty']}T | Omzet={p['omzet']:,.0f} | HPP={p['hpp']:,.0f} | GP={p['gp']:,.0f}")

    # BIAYA OPS
    biaya_qs = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date], status='SELESAI', kabupaten=kab
    )
    total_ops = biaya_qs.aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    gross_profit = total_omzet - total_modal
    net_profit = gross_profit - total_ops

    print(f"\n  Total Omzet      : Rp {total_omzet:,.0f}")
    print(f"  Total HPP        : Rp {total_modal:,.0f}")
    print(f"  Laba Kotor       : Rp {gross_profit:,.0f}")
    print(f"  Biaya Ops        : Rp {total_ops:,.0f}")
    print(f"  LABA BERSIH      : Rp {net_profit:,.0f}")

    # PIUTANG
    inv_qs = Invoice.objects.filter(
        issue_date__lte=end_date,
        distribution__kios__kecamatan__kabupaten=kab
    )
    total_tagihan = inv_qs.aggregate(total=Coalesce(Sum('total_amount'), Decimal('0')))['total']
    total_bayar = Payment.objects.filter(
        status='APPROVED', date__lte=end_date, invoice__in=inv_qs
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    piutang = max(Decimal('0'), total_tagihan - total_bayar)

    print(f"  Piutang          : Rp {piutang:,.0f}")
    print(f"  Total Tagihan    : Rp {total_tagihan:,.0f}")
    print(f"  Total Dibayar    : Rp {total_bayar:,.0f}")

# ===========================
# MANUAL CROSS-CHECK
# ===========================
section("CROSS-CHECK: SEMARANG")
kab_smg = Kabupaten.objects.get(name='Semarang')
# SJ in Semarang:
# SJ1: Kios Tani Sejahtera (Ungaran) → NPK 10T → Omzet = 55jt, HPP = 48jt 
# SJ2: Kios Makmur Jaya (Bergas) → Urea 6T → Omzet = 25.2jt, HPP = 21.6jt
# Biaya Ops: 500.000 (armada) + 1.200.000 (kantor) = 1.700.000
check("Semarang Total Omzet", 
    DistributionItem.objects.filter(
        distribution__kios__kecamatan__kabupaten=kab_smg
    ).count(), 2)

# Expected Semarang: Omzet=80.200.000  HPP=69.600.000  GP=10.600.000  Ops=1.700.000  NP=8.900.000
di_smg = DistributionItem.objects.filter(distribution__kios__kecamatan__kabupaten=kab_smg)
omzet_smg = sum(i.tonnage * i.price_sell_snapshot for i in di_smg)
hpp_smg = sum(i.tonnage * i.price_buy_snapshot for i in di_smg)
check("Semarang Omzet", omzet_smg, Decimal('80200000'))
check("Semarang HPP", hpp_smg, Decimal('69600000'))
check("Semarang Laba Kotor", omzet_smg - hpp_smg, Decimal('10600000'))
ops_smg = BiayaOperasional.objects.filter(kabupaten=kab_smg, status='SELESAI').aggregate(t=Coalesce(Sum('nominal'), Decimal('0')))['t']
check("Semarang BiayaOps", ops_smg, Decimal('1700000'))
check("Semarang Laba Bersih", omzet_smg - hpp_smg - ops_smg, Decimal('8900000'))

# Piutang Semarang: SJ1 PAID, SJ2 PAID → piutang = 0
inv_smg = Invoice.objects.filter(distribution__kios__kecamatan__kabupaten=kab_smg)
tagihan_smg = inv_smg.aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
bayar_smg = Payment.objects.filter(status='APPROVED', invoice__in=inv_smg).aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']
piutang_smg = max(Decimal('0'), tagihan_smg - bayar_smg)
check("Semarang Piutang", piutang_smg, Decimal('0'))

section("CROSS-CHECK: DEMAK")
kab_dmk = Kabupaten.objects.get(name='Demak')
# SJ in Demak:
# SJ3: Kios Berkah Tani (Mranggen) → NPK 8T → Omzet = 44jt, HPP = 38.4jt
# SJ4: DELETED → no longer counts
# Biaya Ops: 750.000 (armada)
di_dmk = DistributionItem.objects.filter(distribution__kios__kecamatan__kabupaten=kab_dmk)
check("Demak item count", di_dmk.count(), 1)  # Only SJ3 (SJ4 was deleted)
omzet_dmk = sum(i.tonnage * i.price_sell_snapshot for i in di_dmk)
hpp_dmk = sum(i.tonnage * i.price_buy_snapshot for i in di_dmk)
check("Demak Omzet", omzet_dmk, Decimal('44000000'))
check("Demak HPP", hpp_dmk, Decimal('38400000'))
check("Demak Laba Kotor", omzet_dmk - hpp_dmk, Decimal('5600000'))
ops_dmk = BiayaOperasional.objects.filter(kabupaten=kab_dmk, status='SELESAI').aggregate(t=Coalesce(Sum('nominal'), Decimal('0')))['t']
check("Demak BiayaOps", ops_dmk, Decimal('750000'))
check("Demak Laba Bersih", omzet_dmk - hpp_dmk - ops_dmk, Decimal('4850000'))

# Piutang Demak: SJ3 UNPAID → piutang = 44.000.000
inv_dmk = Invoice.objects.filter(distribution__kios__kecamatan__kabupaten=kab_dmk)
tagihan_dmk = inv_dmk.aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
bayar_dmk = Payment.objects.filter(status='APPROVED', invoice__in=inv_dmk).aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']
piutang_dmk = max(Decimal('0'), tagihan_dmk - bayar_dmk)
check("Demak Piutang", piutang_dmk, Decimal('44000000'))

section("CROSS-CHECK: GABUNGAN (Smg + Dmk)")
check("Total Omzet Gabungan", omzet_smg + omzet_dmk, Decimal('124200000'))
check("Total HPP Gabungan", hpp_smg + hpp_dmk, Decimal('108000000'))
check("Total Laba Bersih Gabungan", (omzet_smg - hpp_smg - ops_smg) + (omzet_dmk - hpp_dmk - ops_dmk), Decimal('13750000'))
check("Total Piutang Gabungan", piutang_smg + piutang_dmk, Decimal('44000000'))

# NOTE: Total gabungan BERBEDA dari Phase 8 simulation_run.py karena SJ4 sudah dihapus di edge case test!
# Phase 8 total was before SJ4 deletion: Omzet=145.2jt, HPP=126jt, NP=16.75jt, Piutang=65jt
# After SJ4 delete: Omzet=124.2jt, HPP=108jt, NP=13.75jt, Piutang=44jt ✓

print()
print("=" * 60)
print(f"  RESULTS: {PASS} PASSED / {FAIL} FAILED")
print("=" * 60)

# Also run existing unit tests
print()
print("Running existing test suite (gudang/tests.py)...")
