"""
SETUP MASTER DATA — Siap Operasional Manual
=============================================
Script ini menyiapkan SEMUA master data agar user bisa langsung
melakukan operasional secara manual di website:
  - Catatan Order
  - Penebusan (SO)
  - Transfer Gudang
  - Distribusi / Surat Jalan
  - Lihat Kartu Stok

Jalankan:
  python manage.py flush --no-input
  python setup_master_data.py

Login: admin / admin123
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sim_dp.settings')
django.setup()

from django.contrib.auth.models import User, Group
from core.models import (
    CompanyProfile, Kabupaten, Kecamatan, JenisPupuk,
    FertilizerPrice, Kios, KiosAllocation, Armada,
)
from decimal import Decimal
from datetime import date

year = date.today().year

def ok(msg):
    print(f"  \033[92m✓\033[0m {msg}")

def header(title):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)

# ═══════════════════════════════════════
header("1. USER & GROUP")
# ═══════════════════════════════════════

grp_owner, _ = Group.objects.get_or_create(name='Owner')
grp_staff, _ = Group.objects.get_or_create(name='Staff Gudang')

admin = User.objects.create_superuser('admin', 'admin@berkahtani.co.id', 'admin123')
admin.first_name = 'Admin'
admin.last_name = 'Owner'
admin.save()
admin.groups.add(grp_owner)
ok("Superuser: admin / admin123 (Owner)")

staff = User.objects.create_user('gudang', 'gudang@berkahtani.co.id', 'gudang123', is_staff=True)
staff.first_name = 'Staff'
staff.last_name = 'Gudang'
staff.save()
staff.groups.add(grp_staff)
ok("Staff: gudang / gudang123 (Staff Gudang)")

# ═══════════════════════════════════════
header("2. PROFIL PERUSAHAAN")
# ═══════════════════════════════════════

company = CompanyProfile.objects.create(
    name='CV. BERKAH TANI NUSANTARA',
    address='Jl. Raya Salatiga - Semarang KM 5, Kab. Semarang, Jawa Tengah',
    phone='0812-3456-7890',
    email='info@berkahtani.co.id',
    bank_name='Bank BCA',
    bank_account='123-456-7890',
    bank_account_name='CV Berkah Tani Nusantara',
)
ok(f"Perusahaan: {company.name}")

# ═══════════════════════════════════════
header("3. WILAYAH (KABUPATEN & KECAMATAN)")
# ═══════════════════════════════════════

wilayah = {
    'Kab. Semarang': ['Ungaran Barat', 'Ungaran Timur', 'Ambarawa', 'Banyubiru', 'Bergas'],
    'Kab. Kendal': ['Weleri', 'Kaliwungu', 'Boja', 'Pegandon'],
    'Kab. Demak': ['Demak', 'Sayung', 'Karangawen', 'Guntur'],
}

all_kab = {}
all_kec = {}
for kab_name, kec_list in wilayah.items():
    kab = Kabupaten.objects.create(name=kab_name, is_active=True)
    all_kab[kab_name] = kab
    for kec_name in kec_list:
        kec = Kecamatan.objects.create(name=kec_name, kabupaten=kab)
        all_kec[kec_name] = kec
    ok(f"{kab_name}: {', '.join(kec_list)}")

# ═══════════════════════════════════════
header("4. JENIS PUPUK")
# ═══════════════════════════════════════

pupuk_data = [
    ('NPK Phonska', 'NPK'),
    ('Urea', 'UREA'),
    ('ZA', 'ZA'),
    ('SP-36', 'SP36'),
]
all_pupuk = {}
for name, code in pupuk_data:
    jp = JenisPupuk.objects.create(name=name, code=code, is_active=True)
    all_pupuk[code] = jp
    ok(f"{name} ({code})")

# ═══════════════════════════════════════
header("5. HARGA PUPUK (per Ton per Kabupaten)")
# ═══════════════════════════════════════

# Harga bervariasi per kabupaten untuk realistis
harga = {
    'Kab. Semarang': {
        'NPK':  (Decimal('4800000'), Decimal('5500000')),  # (beli, jual)
        'UREA': (Decimal('3600000'), Decimal('4200000')),
        'ZA':   (Decimal('3000000'), Decimal('3500000')),
        'SP36': (Decimal('3200000'), Decimal('3800000')),
    },
    'Kab. Kendal': {
        'NPK':  (Decimal('4850000'), Decimal('5550000')),
        'UREA': (Decimal('3650000'), Decimal('4250000')),
        'ZA':   (Decimal('3050000'), Decimal('3550000')),
        'SP36': (Decimal('3250000'), Decimal('3850000')),
    },
    'Kab. Demak': {
        'NPK':  (Decimal('4900000'), Decimal('5600000')),
        'UREA': (Decimal('3700000'), Decimal('4300000')),
        'ZA':   (Decimal('3100000'), Decimal('3600000')),
        'SP36': (Decimal('3300000'), Decimal('3900000')),
    },
}

for kab_name, prices in harga.items():
    kab = all_kab[kab_name]
    for code, (buy, sell) in prices.items():
        FertilizerPrice.objects.create(
            jenis_pupuk=all_pupuk[code], kabupaten=kab,
            price_buy=buy, price_sell=sell,
        )
    ok(f"{kab_name}: NPK/UREA/ZA/SP36 — harga terdaftar")

print()
print(f"  {'Kabupaten':<18} {'Pupuk':<8} {'Beli/Ton':>14} {'Jual/Ton':>14}")
print(f"  {'-'*18} {'-'*8} {'-'*14} {'-'*14}")
for kab_name, prices in harga.items():
    for code, (buy, sell) in prices.items():
        print(f"  {kab_name:<18} {code:<8} {buy:>14,.0f} {sell:>14,.0f}")

# ═══════════════════════════════════════
header("6. KIOS & ALOKASI KUOTA")
# ═══════════════════════════════════════

kios_data = [
    # (nama, PIC, kecamatan, alamat, phone)
    ('Kios Tani Makmur',   'Pak Budi',    'Ungaran Barat',  'Jl. Ungaran Raya No.10',      '0812-1111-0001'),
    ('Kios Subur Jaya',    'Bu Sari',     'Ambarawa',       'Jl. Ambarawa No.25',           '0812-1111-0002'),
    ('Kios Maju Tani',     'Pak Agus',    'Bergas',         'Jl. Industri Bergas No.8',     '0812-1111-0003'),
    ('Kios Berkah Pupuk',  'Pak Hendra',  'Weleri',         'Jl. Raya Weleri No.15',        '0812-2222-0001'),
    ('Kios Tani Sejahtera','Bu Wati',     'Boja',           'Jl. Boja Raya No.33',          '0812-2222-0002'),
    ('Kios Harapan Tani',  'Pak Darmawan','Demak',          'Jl. Sultan Fatah No.45, Demak','0812-3333-0001'),
    ('Kios Sumber Tani',   'Pak Sugeng',  'Sayung',         'Jl. Raya Sayung No.12',        '0812-3333-0002'),
    ('Kios Padi Emas',     'Bu Lestari',  'Karangawen',     'Jl. Karangawen No.7',          '0812-3333-0003'),
]

# Kuota per kios per jenis pupuk (ton/tahun)
kuota_template = {
    'NPK':  Decimal('50'),
    'UREA': Decimal('40'),
    'ZA':   Decimal('25'),
    'SP36': Decimal('20'),
}

all_kios = []
for nama, pic, kec_name, alamat, phone in kios_data:
    kec = all_kec[kec_name]
    kios = Kios.objects.create(
        name=nama, pic_name=pic, kecamatan=kec,
        address=alamat, phone=phone, is_active=True,
    )
    all_kios.append(kios)
    for code, ton in kuota_template.items():
        KiosAllocation.objects.create(
            kios=kios, jenis_pupuk=all_pupuk[code], year=year,
            quota_original=ton, quota_remaining=ton,
        )
    ok(f"{nama} ({kec_name}) — Kuota: NPK {kuota_template['NPK']}T, UREA {kuota_template['UREA']}T, ZA {kuota_template['ZA']}T, SP36 {kuota_template['SP36']}T")

# ═══════════════════════════════════════
header("7. ARMADA")
# ═══════════════════════════════════════

armada_data = [
    ('H-1234-AB', 'Supri',     'Truk Engkel'),
    ('H-5678-CD', 'Joko',      'Truk Fuso'),
    ('H-9012-EF', 'Wahyu',     'Truk CDD'),
    ('K-3456-GH', 'Bambang',   'Truk Engkel'),
]

for plat, driver, jenis in armada_data:
    Armada.objects.create(
        plate_number=plat, driver_name=driver,
        vehicle_type=jenis, is_active=True,
    )
    ok(f"{plat} — {driver} ({jenis})")

# ═══════════════════════════════════════
header("RINGKASAN")
# ═══════════════════════════════════════

print(f"""
  Kabupaten   : {Kabupaten.objects.count()} ({', '.join(k.name for k in Kabupaten.objects.all())})
  Kecamatan   : {Kecamatan.objects.count()}
  Jenis Pupuk : {JenisPupuk.objects.count()} ({', '.join(j.code for j in JenisPupuk.objects.all())})
  Harga Pupuk : {FertilizerPrice.objects.count()} entri (per kabupaten)
  Kios        : {len(all_kios)}
  Alokasi     : {KiosAllocation.objects.count()} entri (per kios × per pupuk)
  Armada      : {len(armada_data)}

  Login Website:
    Owner : admin / admin123
    Staff : gudang / gudang123

  Silakan buka http://127.0.0.1:8000/ dan mulai operasional:
    1. Buat Catatan Order
    2. Buat Penebusan (SO) + alokasi kecamatan
    3. Transfer ke Gudang (dari SO)
    4. Buat Distribusi / Surat Jalan
    5. Lihat Kartu Stok (Virtual & Fisik)
    6. Lihat Invoice & Pembayaran
""")
