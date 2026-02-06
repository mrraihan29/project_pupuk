"""
SIMULATION SETUP SCRIPT
========================
Membuat semua master data untuk testing end-to-end.
Jalankan: python manage.py shell < simulation_setup.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sim_dp.settings')
django.setup()

from django.contrib.auth.models import User, Group
from core.models import (
    CompanyProfile, Kabupaten, Kecamatan, JenisPupuk,
    FertilizerPrice, Kios, KiosAllocation, Armada, UserProfile
)
from decimal import Decimal
from datetime import date

print("=" * 60)
print("PHASE 1: SETUP MASTER DATA")
print("=" * 60)

# 1. SUPERUSER
admin = User.objects.create_superuser('admin', 'admin@simdp.com', 'admin123')
print(f"[OK] Superuser: admin / admin123")

# 2. GROUPS
grp_owner, _ = Group.objects.get_or_create(name='Owner')
grp_staff, _ = Group.objects.get_or_create(name='Staff Gudang')
print(f"[OK] Groups: Owner, Staff Gudang")

# 3. COMPANY PROFILE
company = CompanyProfile.objects.create(
    name='PT PUPUK NUSANTARA DISTRIBUSI',
    address='Jl. Raya Semarang - Solo KM 12, Ungaran, Semarang',
    phone='024-6921234',
    email='info@pupuknusantara.co.id',
    bank_name='BCA',
    bank_account='1234567890',
    bank_account_name='PT Pupuk Nusantara Distribusi',
)
print(f"[OK] Company: {company.name}")

# 4. KABUPATEN
kab_smg = Kabupaten.objects.create(name='Semarang', is_active=True)
kab_dmk = Kabupaten.objects.create(name='Demak', is_active=True)
print(f"[OK] Kabupaten: {kab_smg.name}, {kab_dmk.name}")

# 5. KECAMATAN
kec_ungaran = Kecamatan.objects.create(name='Ungaran', kabupaten=kab_smg)
kec_bergas = Kecamatan.objects.create(name='Bergas', kabupaten=kab_smg)
kec_mranggen = Kecamatan.objects.create(name='Mranggen', kabupaten=kab_dmk)
kec_karangawen = Kecamatan.objects.create(name='Karangawen', kabupaten=kab_dmk)
print(f"[OK] Kecamatan: Ungaran, Bergas (Semarang); Mranggen, Karangawen (Demak)")

# 6. JENIS PUPUK
npk = JenisPupuk.objects.create(name='NPK Phonska', code='NPK', is_active=True)
urea = JenisPupuk.objects.create(name='Urea', code='UREA', is_active=True)
print(f"[OK] Jenis Pupuk: {npk.code}, {urea.code}")

# 7. HARGA PUPUK PER KABUPATEN
# Semarang
FertilizerPrice.objects.create(
    jenis_pupuk=npk, kabupaten=kab_smg,
    price_sell=Decimal('5500000'), price_buy=Decimal('4800000')
)
FertilizerPrice.objects.create(
    jenis_pupuk=urea, kabupaten=kab_smg,
    price_sell=Decimal('4200000'), price_buy=Decimal('3600000')
)
# Demak
FertilizerPrice.objects.create(
    jenis_pupuk=npk, kabupaten=kab_dmk,
    price_sell=Decimal('5500000'), price_buy=Decimal('4800000')
)
FertilizerPrice.objects.create(
    jenis_pupuk=urea, kabupaten=kab_dmk,
    price_sell=Decimal('4200000'), price_buy=Decimal('3600000')
)
print(f"[OK] Harga: NPK Jual=5.5jt/Buy=4.8jt | Urea Jual=4.2jt/Buy=3.6jt (per ton)")

# 8. KIOS (2 per kabupaten = 4 total)
current_year = date.today().year
kios_data = [
    # (name, address, pic_name, phone, kecamatan, alokasi: [(jenis, ton)])
    ('Kios Tani Sejahtera', 'Jl. Ungaran Raya No.45', 'Pak Budi', '0812-1111-0001', kec_ungaran,
     [(npk, 25), (urea, 15)]),
    ('Kios Makmur Jaya', 'Jl. Bergas Kidul No.12', 'Pak Eko', '0812-1111-0002', kec_bergas,
     [(npk, 25), (urea, 15)]),
    ('Kios Berkah Tani', 'Jl. Mranggen Baru No.8', 'Bu Siti', '0812-1111-0003', kec_mranggen,
     [(npk, 20), (urea, 10)]),
    ('Kios Subur Makmur', 'Jl. Karangawen Raya No.33', 'Pak Wawan', '0812-1111-0004', kec_karangawen,
     [(npk, 20), (urea, 10)]),
]

kios_objs = {}
for name, addr, pic, phone, kec, allocs in kios_data:
    kios = Kios.objects.create(
        name=name, address=addr, pic_name=pic, phone=phone,
        kecamatan=kec, is_active=True
    )
    for jenis, ton in allocs:
        KiosAllocation.objects.create(
            kios=kios, jenis_pupuk=jenis, year=current_year,
            quota_original=Decimal(str(ton)), quota_remaining=Decimal(str(ton))
        )
    kios_objs[name] = kios
    kab_name = kec.kabupaten.name
    print(f"[OK] Kios: {name} ({kec.name}, {kab_name}) | Alokasi: {', '.join(f'{j.code}={t}T' for j,t in allocs)}")

# 9. ARMADA
armada1 = Armada.objects.create(
    plate_number='H-1234-AB', driver_name='Supri',
    vehicle_type='Truk Engkel', is_active=True
)
armada2 = Armada.objects.create(
    plate_number='K-5678-CD', driver_name='Joko',
    vehicle_type='Truk Fuso', is_active=True
)
print(f"[OK] Armada: {armada1.plate_number} ({armada1.driver_name}), {armada2.plate_number} ({armada2.driver_name})")

# 10. USERS
# User Owner Semarang
user_owner = User.objects.create_user('owner_smg', password='test1234', is_staff=True)
user_owner.groups.add(grp_owner)
# Signal auto-creates UserProfile, so update kabupaten on existing profile
user_owner.profile.kabupaten = kab_smg
user_owner.profile.save()

# User Staff Demak
user_staff = User.objects.create_user('staff_dmk', password='test1234', is_staff=False)
user_staff.groups.add(grp_staff)
user_staff.profile.kabupaten = kab_dmk
user_staff.profile.save()

print(f"[OK] User: owner_smg (Owner, Semarang) / test1234")
print(f"[OK] User: staff_dmk (Staff Gudang, Demak) / test1234")

print()
print("=" * 60)
print("SETUP SELESAI! Master data siap digunakan.")
print("=" * 60)
print()

# Summary
print("RINGKASAN DATA:")
print(f"  Kabupaten    : {Kabupaten.objects.count()}")
print(f"  Kecamatan    : {Kecamatan.objects.count()}")
print(f"  Jenis Pupuk  : {JenisPupuk.objects.count()}")
print(f"  Harga Pupuk  : {FertilizerPrice.objects.count()}")
print(f"  Kios         : {Kios.objects.count()}")
print(f"  Alokasi Kios : {KiosAllocation.objects.count()}")
print(f"  Armada       : {Armada.objects.count()}")
print(f"  Users        : {User.objects.count()}")
