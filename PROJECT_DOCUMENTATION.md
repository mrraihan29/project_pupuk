# 📘 SIM-DP (Sistem Informasi Manajemen Distribusi Pupuk)
## Dokumentasi Teknis Komprehensif untuk Developer

> **Versi Dokumen:** 1.0  
> **Tanggal:** Februari 2026  
> **Framework:** Django 5.0 | Python 3.11 | PostgreSQL  
> **Status:** Production Ready

---

## 📑 DAFTAR ISI

1. [Pendahuluan & Gambaran Umum](#1-pendahuluan--gambaran-umum)
2. [Technology Stack](#2-technology-stack)
3. [Struktur Project](#3-struktur-project)
4. [Database Schema & Relationship](#4-database-schema--relationship)
5. [Alur Bisnis Utama (Main Business Flow)](#5-alur-bisnis-utama-main-business-flow)
6. [Modul CORE - Master Data](#6-modul-core---master-data)
7. [Modul GUDANG - Operasional](#7-modul-gudang---operasional)
8. [Modul KEUANGAN - Finance](#8-modul-keuangan---finance)
9. [Multi-Kabupaten Access Control](#9-multi-kabupaten-access-control)
10. [Signal-Driven Automation](#10-signal-driven-automation)
11. [URL Routing & Endpoints](#11-url-routing--endpoints)
12. [Template Structure](#12-template-structure)
13. [Validasi & Business Rules](#13-validasi--business-rules)
14. [Deployment & Configuration](#14-deployment--configuration)
15. [Troubleshooting Guide](#15-troubleshooting-guide)

---

## 1. PENDAHULUAN & GAMBARAN UMUM

### 1.1 Apa itu SIM-DP?

**SIM-DP (Sistem Informasi Manajemen Distribusi Pupuk)** adalah aplikasi web enterprise untuk mengelola distribusi pupuk bersubsidi dari distributor ke kios-kios pengecer. Aplikasi ini menangani:

- **Master Data:** Jenis pupuk, harga, kios mitra, armada pengiriman, wilayah
- **Operasional Gudang:** Penebusan dari pabrik, transfer stok, distribusi ke kios
- **Keuangan:** Invoice otomatis, pembayaran, biaya operasional, laporan laba rugi
- **Multi-Tenant:** Satu aplikasi untuk banyak kabupaten dengan isolasi data

### 1.2 Konsep Stok Dual-Layer

Aplikasi ini menggunakan konsep **Dual Stock Management**:

| Tipe Stok | Lokasi | Keterangan |
|-----------|--------|------------|
| **VIRTUAL** | Pabrik/Gudang Asal | Barang sudah milik kita tapi fisiknya masih di pabrik |
| **PHYSICAL** | Gudang Penyangga | Barang sudah ada secara fisik di gudang kita |

### 1.3 Stakeholder & User Roles

| Role | Deskripsi | Akses |
|------|-----------|-------|
| **Superuser** | Administrator sistem | Semua data, semua kabupaten |
| **Admin Kabupaten** | Pengelola per wilayah | Data sesuai kabupaten yang di-assign |
| **Staff** | Operator harian | Input transaksi sesuai kabupaten |
| **Owner** | Pemilik/Direktur | Approval biaya operasional |

---

## 2. TECHNOLOGY STACK

### 2.1 Backend

```
Framework       : Django 5.0
Language        : Python 3.11
Database        : PostgreSQL
ORM             : Django ORM
Authentication  : Django Auth + Custom Profile
```

### 2.2 Frontend

```
CSS Framework   : Bootstrap 5.3.0
Icons           : Bootstrap Icons 1.11.0
Fonts           : Google Fonts (Poppins)
JavaScript      : Vanilla JS (no framework)
```

### 2.3 Infrastructure & Deployment

```
Web Server      : Gunicorn
Static Files    : Whitenoise (compressed + cached)
Container       : Docker
Orchestration   : Coolify (self-hosted PaaS)
Storage         : Local / Cloudflare R2 (S3-compatible)
```

### 2.4 Dependencies Penting (requirements.txt)

```
Django==5.0                 # Web Framework
psycopg2-binary==2.9.9      # PostgreSQL adapter
gunicorn==21.2.0            # WSGI Server
whitenoise==6.6.0           # Static files serving
python-dotenv==1.0.0        # Environment variables
xhtml2pdf==0.2.17           # PDF generation
reportlab==4.4.6            # PDF engine
pillow==12.0.0              # Image processing
django-storages==1.14.6     # S3/R2 storage backend
boto3==1.42.17              # AWS SDK for R2
```

---

## 3. STRUKTUR PROJECT

```
project_pupuk/
│
├── sim_dp/                          # Django Project Configuration
│   ├── __init__.py
│   ├── settings.py                  # ⭐ Konfigurasi utama (DB, Storage, dll)
│   ├── urls.py                      # Root URL routing
│   ├── wsgi.py                      # WSGI entry point
│   └── asgi.py                      # ASGI entry point (unused)
│
├── core/                            # 📦 APP: Master Data & Laporan
│   ├── models.py                    # ⭐ Model: Kabupaten, Kecamatan, Kios, Pupuk, dll
│   ├── views.py                     # ⭐ View: Dashboard, Laporan Keuangan, CRUD Master
│   ├── forms.py                     # Form classes untuk input data
│   ├── urls.py                      # URL routing untuk core
│   ├── admin.py                     # Django Admin configuration
│   ├── signals.py                   # Auto-create UserProfile
│   ├── utils.py                     # ⭐ Helper: scope_by_kabupaten, get_price
│   ├── context_processors.py        # Inject user_groups ke template
│   ├── decorators.py                # @owner_required decorator
│   └── migrations/                  # Database migrations
│
├── gudang/                          # 📦 APP: Operasional Gudang
│   ├── models.py                    # ⭐ Model: SO, Transfer, Distribution, StockCard
│   ├── views.py                     # ⭐ View: CRUD transaksi gudang
│   ├── forms.py                     # Form classes untuk transaksi
│   ├── urls.py                      # URL routing untuk gudang
│   ├── admin.py                     # Django Admin configuration
│   ├── signals.py                   # ⭐⭐ KRITIS: Auto-update StockCard & Kuota
│   └── migrations/                  # Database migrations
│
├── keuangan/                        # 📦 APP: Finance & Accounting
│   ├── models.py                    # Model: Invoice, Payment, BiayaOperasional
│   ├── views.py                     # View: Invoice list, Payment, Biaya
│   ├── forms.py                     # Form classes
│   ├── urls.py                      # URL routing untuk keuangan
│   ├── admin.py                     # Django Admin configuration
│   ├── signals.py                   # ⭐ Auto-create Invoice dari Distribution
│   └── migrations/                  # Database migrations
│
├── templates/                       # 🎨 HTML Templates
│   ├── base.html                    # ⭐ Layout utama (sidebar, navbar, messages)
│   ├── dashboard.html               # Halaman utama setelah login
│   ├── core/                        # Templates untuk app core
│   ├── gudang/                      # Templates untuk app gudang
│   ├── keuangan/                    # Templates untuk app keuangan
│   ├── setup/                       # Templates untuk halaman setup
│   └── registration/                # Login page
│
├── static/                          # 📁 Static Assets (development)
│   ├── css/app.css                  # Custom CSS (sidebar, tables, dll)
│   ├── js/layout.js                 # JavaScript untuk sidebar interaction
│   └── vendor/                      # Bootstrap, Icons (local fallback)
│
├── staticfiles/                     # 📁 Collected static (production)
├── media/                           # 📁 User uploads (bukti, foto)
│
├── manage.py                        # Django CLI
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Container build instructions
├── README.md                        # Quick start guide
├── DEPLOY_HOSTINGER_COOLIFY.md      # Deployment guide
├── workflow.md                      # User workflow guide
├── review.md                        # Development checklist
└── flowchart.mmd                    # Mermaid flowchart
```

---

## 4. DATABASE SCHEMA & RELATIONSHIP

### 4.1 Entity Relationship Diagram (Simplified)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MASTER DATA (core)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐               │
│  │  Kabupaten   │──1:N─│  Kecamatan   │──1:N─│     Kios     │               │
│  └──────────────┘      └──────────────┘      └──────────────┘               │
│         │                                           │                        │
│         │                                           │                        │
│         │              ┌──────────────┐             │                        │
│         └──────────────│FertilizerPrice│            │                        │
│                        └──────────────┘             │                        │
│                              │                      │                        │
│                        ┌──────────────┐      ┌──────────────┐               │
│                        │  JenisPupuk  │──────│KiosAllocation│               │
│                        └──────────────┘      └──────────────┘               │
│                                                                              │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐               │
│  │    Armada    │      │ UserProfile  │──────│  Django User │               │
│  └──────────────┘      └──────────────┘      └──────────────┘               │
│                              │                                               │
│                              └───────────────── Kabupaten                    │
│                                                                              │
│  ┌──────────────┐                                                            │
│  │CompanyProfile│  (Singleton - 1 record only)                               │
│  └──────────────┘                                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           GUDANG (gudang)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐      ┌──────────────────┐                                 │
│  │  SalesOrder  │──1:N─│SalesOrderAllocation│──────── Kecamatan             │
│  └──────────────┘      └──────────────────┘                                 │
│         │                                                                    │
│         │──────────────────────────────────────────┐                        │
│         │                                          │                        │
│  ┌──────────────────┐                    ┌──────────────────┐               │
│  │WarehouseTransfer │                    │   Distribution   │               │
│  └──────────────────┘                    └──────────────────┘               │
│         │                                          │                        │
│         │                                          │──1:N─┐                 │
│         │                                          │      │                 │
│         │                                ┌──────────────────┐               │
│         │                                │DistributionItem  │               │
│         │                                └──────────────────┘               │
│         │                                          │                        │
│         └──────────────────┬───────────────────────┘                        │
│                            │                                                 │
│                     ┌──────────────┐                                        │
│                     │  StockCard   │  (LEDGER - Single Source of Truth)     │
│                     └──────────────┘                                        │
│                                                                              │
│  ┌──────────────┐      ┌──────────────────┐                                 │
│  │  OrderNote   │──1:N─│  OrderNoteItem   │                                 │
│  └──────────────┘      └──────────────────┘                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           KEUANGAN (keuangan)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐                    ┌──────────────┐                       │
│  │ Distribution │──1:1 (auto)────────│   Invoice    │                       │
│  └──────────────┘                    └──────────────┘                       │
│                                             │                                │
│                                             │──1:N                           │
│                                             │                                │
│                                      ┌──────────────┐                       │
│                                      │   Payment    │                       │
│                                      └──────────────┘                       │
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │ BiayaOperasional │──────── Armada (optional)                             │
│  └──────────────────┘──────── Kabupaten                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Model Details - CORE

#### Kabupaten
```python
class Kabupaten(models.Model):
    name = CharField(max_length=100, unique=True)    # Nama Kabupaten
    code = CharField(max_length=10, blank=True)      # Kode (opsional)
    is_active = BooleanField(default=True)           # Status aktif
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

#### Kecamatan
```python
class Kecamatan(models.Model):
    name = CharField(max_length=100, unique=True)    # Nama Kecamatan
    code = CharField(max_length=10, blank=True)      # Kode Wilayah
    kabupaten = ForeignKey(Kabupaten, PROTECT)       # ⭐ Relasi ke Kabupaten
```

#### JenisPupuk
```python
class JenisPupuk(models.Model):
    name = CharField(max_length=50, unique=True)     # NPK, UREA, dll
    code = CharField(max_length=10, unique=True)     # Kode singkat
    color = CharField(max_length=20, default='primary')  # Warna UI
    is_active = BooleanField(default=True)           # Bisa diarsipkan
```

#### FertilizerPrice (Harga per Kabupaten)
```python
class FertilizerPrice(models.Model):
    jenis_pupuk = ForeignKey(JenisPupuk, CASCADE)
    kabupaten = ForeignKey(Kabupaten, PROTECT)       # ⭐ Harga per kabupaten
    price_buy = DecimalField(max_digits=15)          # Harga beli (per TON)
    price_sell = DecimalField(max_digits=15)         # Harga jual (per TON)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('jenis_pupuk', 'kabupaten')  # 1 harga per pupuk per kab
```

#### Kios
```python
class Kios(models.Model):
    name = CharField(max_length=100)                 # Nama Kios
    pic_name = CharField(max_length=100)             # Penanggung Jawab
    kecamatan = ForeignKey(Kecamatan, PROTECT)       # ⭐ Lokasi kios
    address = TextField()                            # Alamat lengkap
    phone = CharField(max_length=20)                 # Kontak
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
```

#### KiosAllocation (Kuota Tahunan)
```python
class KiosAllocation(models.Model):
    kios = ForeignKey(Kios, CASCADE, related_name='allocations')
    year = IntegerField(default=current_year)        # Tahun anggaran
    jenis_pupuk = ForeignKey(JenisPupuk, CASCADE)
    quota_original = DecimalField()                  # Jatah awal (Ton)
    quota_remaining = DecimalField()                 # Sisa kuota (Ton)
    
    # Property: quota_used = quota_original - quota_remaining
    
    class Meta:
        unique_together = ('kios', 'year', 'jenis_pupuk')
```

#### UserProfile (Kabupaten Assignment)
```python
class UserProfile(models.Model):
    user = OneToOneField(User, CASCADE, related_name='profile')
    kabupaten = ForeignKey(Kabupaten, PROTECT, null=True)  # ⭐ Isolasi data
```

### 4.3 Model Details - GUDANG

#### SalesOrder (Penebusan)
```python
class SalesOrder(models.Model):
    so_number = CharField(max_length=50, unique=True)    # Nomor SO pabrik
    date = DateField()                                   # Tanggal penebusan
    jenis_pupuk = ForeignKey(JenisPupuk, PROTECT)        # Jenis pupuk
    file_upload = FileField(upload_to='documents/so/')   # Bukti DO/SO
    is_closed = BooleanField(default=False)              # Auto-close jika habis
    
    # Methods:
    # - total_tonnage: Sum dari allocations
    # - get_virtual_balance(): Sisa stok = total - transferred - distributed
```

#### SalesOrderAllocation
```python
class SalesOrderAllocation(models.Model):
    sales_order = ForeignKey(SalesOrder, CASCADE, related_name='allocations')
    kecamatan = ForeignKey(Kecamatan, PROTECT)           # Alokasi per kecamatan
    tonnage = DecimalField()                             # Jumlah (Ton)
```

#### WarehouseTransfer (Tarik ke Gudang)
```python
class WarehouseTransfer(models.Model):
    source_so = ForeignKey(SalesOrder, PROTECT, related_name='transfers')
    date = DateField(default=timezone.now)               # Tanggal masuk gudang
    tonnage = DecimalField()                             # Jumlah ditarik (Ton)
    reference_code = CharField(max_length=50)            # No. Surat Jalan Pabrik
    notes = TextField(blank=True)
    
    # clean(): Validasi stok virtual cukup
```

#### Distribution (Surat Jalan)
```python
class Distribution(models.Model):
    SOURCE_CHOICES = [
        ('VIRTUAL', 'Langsung dari Pabrik'),
        ('PHYSICAL', 'Dari Gudang Penyangga'),
    ]
    
    no_surat_jalan = CharField(max_length=50, unique=True, editable=False)
    date = DateField()                                   # Tanggal kirim
    pkp_date = DateField()                               # Tanggal PKP (admin)
    kios = ForeignKey(Kios, PROTECT)                     # Tujuan
    armada = ForeignKey(Armada, PROTECT)                 # Kendaraan
    source_type = CharField(choices=SOURCE_CHOICES)      # Sumber stok
    source_so = ForeignKey(SalesOrder, null=True)        # Jika VIRTUAL
    jenis_pupuk = ForeignKey(JenisPupuk, PROTECT)        # Legacy header
    tonnage = DecimalField()                             # Legacy header
    driver_name_snapshot = CharField(max_length=100)     # Snapshot supir
    nopol_snapshot = CharField(max_length=20)            # Snapshot nopol
    
    # save(): Auto-generate no_surat_jalan format SJ/YYYYMMDD/XXXX
    # clean(): Validasi stok & kuota
```

#### DistributionItem (Multi-Item per SJ)
```python
class DistributionItem(models.Model):
    distribution = ForeignKey(Distribution, CASCADE, related_name='items')
    jenis_pupuk = ForeignKey(JenisPupuk, PROTECT)
    source_type = CharField(choices=Distribution.SOURCE_CHOICES)
    source_so = ForeignKey(SalesOrder, null=True)        # Jika VIRTUAL
    order_item = ForeignKey(OrderNoteItem, null=True)    # Link ke pesanan
    tonnage = DecimalField()
```

#### StockCard (Ledger - SINGLE SOURCE OF TRUTH)
```python
class StockCard(models.Model):
    STOCK_TYPE_CHOICES = [
        ('VIRTUAL', 'Stok Virtual (SO)'),
        ('PHYSICAL', 'Stok Fisik (Gudang)'),
    ]
    
    TRANSACTION_TYPES = [
        ('IN_SO', 'Penebusan Baru (Virtual In)'),
        ('OUT_TRF', 'Ditarik ke Gudang (Virtual Out)'),
        ('IN_TRF', 'Masuk Gudang (Physical In)'),
        ('IN_DIST_P', 'Distribusi Masuk Gudang (Physical In)'),
        ('OUT_DIST_V', 'Distribusi Langsung (Virtual Out)'),
        ('OUT_DIST_P', 'Distribusi Gudang (Physical Out)'),
        ('ADJUST', 'Penyesuaian / Opname'),
    ]
    
    date = DateField()
    jenis_pupuk = ForeignKey(JenisPupuk, CASCADE)
    stock_type = CharField(choices=STOCK_TYPE_CHOICES)   # VIRTUAL atau PHYSICAL
    transaction_type = CharField(choices=TRANSACTION_TYPES)
    reference_number = CharField(max_length=100)         # No. SO/SJ
    description = CharField(max_length=255)
    qty_in = DecimalField(default=0)                     # Masuk
    qty_out = DecimalField(default=0)                    # Keluar
    balance = DecimalField(default=0)                    # Running balance
```

#### OrderNote & OrderNoteItem (Catatan Pesanan)
```python
class OrderNote(models.Model):
    STATUS_CHOICES = [('OPEN', 'Terbuka'), ('DONE', 'Selesai')]
    
    date = DateField()
    kecamatan = ForeignKey(Kecamatan, PROTECT)
    kios = ForeignKey(Kios, PROTECT)
    notes = TextField(blank=True)
    status = CharField(choices=STATUS_CHOICES, default='OPEN')
    is_deleted = BooleanField(default=False)             # Soft delete

class OrderNoteItem(models.Model):
    order = ForeignKey(OrderNote, CASCADE, related_name='items')
    jenis_pupuk = ForeignKey(JenisPupuk, PROTECT)
    tonnage = DecimalField()
    
    # Properties:
    # - delivered_tonnage: Sum dari DistributionItem yang link ke item ini
    # - remaining_tonnage: tonnage - delivered_tonnage
    # - is_fulfilled: remaining_tonnage <= 0
```

### 4.4 Model Details - KEUANGAN

#### Invoice
```python
class Invoice(models.Model):
    STATUS_CHOICES = [
        ('UNPAID', 'Belum Lunas'),
        ('PARTIAL', 'Cicilan Sebagian'),
        ('PAID', 'Lunas'),
    ]
    
    distribution = OneToOneField(Distribution, CASCADE, related_name='invoice')
    inv_number = CharField(max_length=50, unique=True, editable=False)
    issue_date = DateField()                             # Tanggal terbit
    due_date = DateField()                               # Jatuh tempo (+7 hari)
    total_amount = DecimalField()                        # Total tagihan
    total_paid = DecimalField(default=0)                 # Sudah dibayar
    status = CharField(choices=STATUS_CHOICES, default='UNPAID')
    
    # Property: remaining_balance = total_amount - total_paid
    # Method: update_status() - Auto-update berdasarkan pembayaran
```

#### Payment
```python
class Payment(models.Model):
    STATUS_CHOICES = [
        ('APPROVED', 'Disetujui'),
        ('PENDING', 'Menunggu'),
        ('VOID', 'Void / Batal'),
    ]
    
    invoice = ForeignKey(Invoice, CASCADE, related_name='payments')
    date = DateField(default=timezone.now)
    amount = DecimalField()                              # Jumlah bayar
    method = CharField(default='Transfer Bank')          # Metode
    proof = ImageField(upload_to='keuangan/payment/')    # Bukti
    notes = TextField(blank=True)
    status = CharField(choices=STATUS_CHOICES, default='APPROVED')
    
    # clean(): Validasi amount <= sisa tagihan
```

#### BiayaOperasional
```python
class BiayaOperasional(models.Model):
    KATEGORI_CHOICES = [
        ('ARMADA', 'Biaya Armada (Bensin, Servis, Tol)'),
        ('KANTOR', 'Biaya Kantor (Listrik, ATK, Gaji)'),
        ('LAINNYA', 'Biaya Lain-lain'),
    ]
    
    STATUS_CHOICES = [
        ('PROSES', 'Menunggu Approval Owner'),
        ('SELESAI', 'Disetujui / Selesai'),
        ('TOLAK', 'Ditolak'),
    ]
    
    tanggal = DateField(default=timezone.now)
    kategori_utama = CharField(choices=KATEGORI_CHOICES)
    armada = ForeignKey(Armada, null=True)               # Jika biaya armada
    kabupaten = ForeignKey(Kabupaten, null=True)         # Isolasi data
    deskripsi = TextField()
    nominal = DecimalField()
    bukti_foto = ImageField(upload_to='keuangan/bukti/')
    status = CharField(choices=STATUS_CHOICES, default='PROSES')
```

---

## 5. ALUR BISNIS UTAMA (Main Business Flow)

### 5.1 Flowchart Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ALUR BISNIS SIM-DP                                   │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌─────────────┐
     │   START     │
     └──────┬──────┘
            │
            ▼
┌───────────────────────┐
│ 1. SETUP MASTER DATA  │  (Sekali di awal)
│  - Kabupaten          │
│  - Kecamatan          │
│  - Kios + Alokasi     │
│  - Jenis Pupuk + Harga│
│  - Armada             │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 2. CATATAN ORDER      │  (Opsional - dari permintaan kios)
│  - Input pesanan kios │
│  - Multi-item per order│
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 3. PENEBUSAN (SO)     │  (Barang dari pabrik)
│  - Input No. SO       │
│  - Pilih Jenis Pupuk  │
│  - Alokasi per Kec.   │
│  ─────────────────────│
│  📦 STOK VIRTUAL ++   │
└───────────┬───────────┘
            │
            ├──────────────────────────────────┐
            │                                  │
            ▼                                  ▼
┌───────────────────────┐      ┌───────────────────────┐
│ 4a. TRANSFER GUDANG   │      │ 4b. DISTRIBUSI DIRECT │
│  (Tarik ke fisik)     │      │  (Virtual → Kios)     │
│  ─────────────────────│      │  ─────────────────────│
│  📦 VIRTUAL --        │      │  📦 VIRTUAL --        │
│  📦 PHYSICAL ++       │      │  📄 INVOICE AUTO      │
└───────────┬───────────┘      └───────────┬───────────┘
            │                              │
            ▼                              │
┌───────────────────────┐                  │
│ 4c. DISTRIBUSI GUDANG │                  │
│  (Physical → Kios)    │                  │
│  ─────────────────────│                  │
│  📦 PHYSICAL --       │                  │
│  📄 INVOICE AUTO      │                  │
└───────────┬───────────┘                  │
            │                              │
            └──────────────┬───────────────┘
                           │
                           ▼
┌───────────────────────────────────────────┐
│ 5. PEMBAYARAN                              │
│  - Terima pembayaran dari kios            │
│  - Set status APPROVED/PENDING/VOID       │
│  ─────────────────────────────────────────│
│  💰 Invoice status: UNPAID → PARTIAL → PAID│
└───────────────────┬───────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────┐
│ 6. BIAYA OPERASIONAL                       │
│  - Input biaya (armada/kantor/lain)       │
│  - Status: PROSES (menunggu approval)     │
│  - Owner approve → SELESAI                │
│  ─────────────────────────────────────────│
│  💸 Masuk ke Laporan Laba Rugi            │
└───────────────────┬───────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────┐
│ 7. LAPORAN & MONITORING                    │
│  - Dashboard (piutang, stok)              │
│  - Laporan Laba Rugi                      │
│  - Kartu Stok (ledger)                    │
│  - Raport Kinerja Kios                    │
└───────────────────────────────────────────┘
```

### 5.2 Workflow Detail: Penebusan (SO)

```
┌──────────────────────────────────────────────────────────────────┐
│                    WORKFLOW: PENEBUSAN (SO)                       │
└──────────────────────────────────────────────────────────────────┘

User Input:
├── so_number: "3101-A" (dari pabrik)
├── date: 2026-02-01
├── jenis_pupuk: NPK
├── file_upload: DO_3101A.pdf
└── allocations:
    ├── Kec. Semarang Utara: 50 Ton
    └── Kec. Semarang Barat: 30 Ton

                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     DATABASE OPERATIONS                           │
└──────────────────────────────────────────────────────────────────┘

1. SalesOrder.save()
   └── Create: SO{so_number='3101-A', jenis_pupuk=NPK, date=2026-02-01}

2. SalesOrderAllocation.save() [Signal: post_save]
   ├── Create: Allocation{kecamatan='Semarang Utara', tonnage=50}
   └── Create: Allocation{kecamatan='Semarang Barat', tonnage=30}

3. StockCard.create() [Auto via Signal]
   └── Create: StockCard{
         date: 2026-02-01,
         jenis_pupuk: NPK,
         stock_type: 'VIRTUAL',
         transaction_type: 'IN_SO',
         reference_number: 'SO-{id}',
         description: 'Penebusan 3101-A',
         qty_in: 80,
         qty_out: 0
       }

Result:
├── Stok Virtual NPK: +80 Ton
└── SO Status: is_closed=False
```

### 5.3 Workflow Detail: Distribution (Surat Jalan)

```
┌──────────────────────────────────────────────────────────────────┐
│                  WORKFLOW: DISTRIBUSI (SURAT JALAN)               │
└──────────────────────────────────────────────────────────────────┘

User Input:
├── date: 2026-02-05
├── pkp_date: 2026-02-05
├── kios: "Toko Tani Makmur"
├── armada: "H 1234 AB - Pak Joko"
└── items:
    ├── Item 1: NPK, 10 Ton, VIRTUAL, SO=3101-A
    └── Item 2: UREA, 5 Ton, PHYSICAL, SO=null

                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     VALIDATION (Form + Model)                     │
└──────────────────────────────────────────────────────────────────┘

1. Validate Virtual Stock (Item 1):
   ├── SO 3101-A Virtual Balance = 80 Ton
   └── Request: 10 Ton ✅ (cukup)

2. Validate Physical Stock (Item 2):
   ├── UREA Physical Balance = 20 Ton (dari StockCard)
   └── Request: 5 Ton ✅ (cukup)

3. Validate Kuota Kios:
   ├── KiosAllocation NPK 2026: remaining=50 Ton, request=10 ✅
   └── KiosAllocation UREA 2026: remaining=30 Ton, request=5 ✅

                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     DATABASE OPERATIONS                           │
└──────────────────────────────────────────────────────────────────┘

1. Distribution.save()
   └── Create: Distribution{
         no_surat_jalan='SJ/20260205/A1B2',
         kios='Toko Tani Makmur',
         armada='H 1234 AB'
       }

2. DistributionItem.save() [Signal: post_save per item]

   Item 1 (NPK VIRTUAL):
   ├── StockCard: VIRTUAL OUT (qty_out=10, NPK)
   ├── StockCard: PHYSICAL IN (qty_in=10, NPK) - transit
   ├── StockCard: PHYSICAL OUT (qty_out=10, NPK) - deliver
   └── KiosAllocation: quota_remaining -= 10

   Item 2 (UREA PHYSICAL):
   ├── StockCard: PHYSICAL OUT (qty_out=5, UREA)
   └── KiosAllocation: quota_remaining -= 5

3. Invoice.create() [Auto via Signal on Distribution]
   └── Create: Invoice{
         inv_number='INV/20260205/A1B2',
         issue_date=2026-02-05,
         due_date=2026-02-12,
         total_amount=calculated_from_items,
         status='UNPAID'
       }

Result:
├── Stok Virtual NPK: -10 Ton
├── Stok Fisik UREA: -5 Ton
├── Kuota Kios NPK: -10 Ton
├── Kuota Kios UREA: -5 Ton
├── Invoice: Created (UNPAID)
└── Surat Jalan: Ready to print
```

### 5.4 Workflow Detail: Pembayaran

```
┌──────────────────────────────────────────────────────────────────┐
│                    WORKFLOW: PEMBAYARAN                           │
└──────────────────────────────────────────────────────────────────┘

State Awal:
├── Invoice: INV/20260205/A1B2
├── Total: Rp 50,000,000
├── Paid: Rp 0
└── Status: UNPAID

User Input Payment 1:
├── date: 2026-02-08
├── amount: Rp 30,000,000
├── method: Transfer BCA
├── proof: bukti_tf.jpg
└── status: APPROVED

                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     DATABASE OPERATIONS                           │
└──────────────────────────────────────────────────────────────────┘

1. Payment.save() [Signal: post_save]
   └── Create: Payment{amount=30jt, status='APPROVED'}

2. Invoice.update_status() [Auto via Signal]
   ├── total_paid += 30,000,000
   └── status = 'PARTIAL' (karena paid < total)

State Setelah Payment 1:
├── Total: Rp 50,000,000
├── Paid: Rp 30,000,000
├── Remaining: Rp 20,000,000
└── Status: PARTIAL

User Input Payment 2:
├── amount: Rp 20,000,000
└── status: APPROVED

                    │
                    ▼

State Setelah Payment 2:
├── Total: Rp 50,000,000
├── Paid: Rp 50,000,000
├── Remaining: Rp 0
└── Status: PAID ✅
```

---

## 6. MODUL CORE - MASTER DATA

### 6.1 Views & Functions

| View | URL | Fungsi |
|------|-----|--------|
| `dashboard` | `/` | Halaman utama: piutang, stok, invoice jatuh tempo |
| `kios_list` | `/kios/` | Daftar kios dengan alokasi & realisasi |
| `kios_create` | `/kios/add/` | Form tambah kios + alokasi |
| `kios_update` | `/kios/edit/<pk>/` | Form edit kios |
| `kios_delete` | `/kios/delete/<pk>/` | Konfirmasi hapus kios |
| `armada_list` | `/armada/` | Daftar armada |
| `armada_create` | `/armada/add/` | Form tambah armada |
| `master_data_pupuk` | `/master-data-pupuk/` | Jenis pupuk + harga dalam 1 halaman |
| `raport_kios` | `/laporan/raport/` | Laporan alokasi vs realisasi |
| `laporan_keuangan` | `/laporan/keuangan/` | Laba rugi + neraca |
| `setup_company_profile` | `/setup/company-profile/` | Edit profil perusahaan |
| `setup_kabupaten` | `/setup/kabupaten/` | CRUD kabupaten |
| `setup_kecamatan` | `/setup/kecamatan/` | CRUD kecamatan |
| `setup_users` | `/setup/users/` | Manajemen user + role |

### 6.2 Dashboard Logic

```python
def dashboard(request):
    # 1. Hitung Total Piutang
    total_piutang = Invoice.filter(status__in=['UNPAID','PARTIAL'])
                          .aggregate(total=Sum(F('total_amount')-F('total_paid')))
    
    # 2. Hitung Stok Virtual & Fisik
    def get_stock_balance(jenis_nama, tipe_stok):
        return StockCard.filter(jenis_pupuk__name=jenis_nama, stock_type=tipe_stok)
                       .aggregate(saldo=Sum('qty_in')-Sum('qty_out'))
    
    virt_npk = get_stock_balance('NPK', 'VIRTUAL')
    virt_urea = get_stock_balance('UREA', 'VIRTUAL')
    phys_npk = get_stock_balance('NPK', 'PHYSICAL')
    phys_urea = get_stock_balance('UREA', 'PHYSICAL')
    
    # 3. Invoice Jatuh Tempo
    invoices_list = Invoice.filter(status__in=['UNPAID','PARTIAL']).order_by('due_date')[:5]
    
    # 4. SO Terlama (belum habis)
    so_expiring = SalesOrder.filter(is_closed=False).order_by('date')[:5]
```

### 6.3 Laporan Keuangan Logic

```python
def laporan_keuangan(request):
    # 1. Filter periode
    start_date = request.GET.get('start', awal_bulan)
    end_date = request.GET.get('end', hari_ini)
    
    # 2. Ambil harga master per kabupaten
    harga_npk = get_price_by_code('NPK', kabupaten)
    harga_urea = get_price_by_code('UREA', kabupaten)
    
    # 3. Hitung Omzet (dari Invoice atau distribusi x harga master)
    qty_jual_npk = DistributionItem.filter(date__range, jenis='NPK').aggregate(Sum('tonnage'))
    omzet_npk = qty_jual_npk * harga_npk.price_sell
    
    # 4. Hitung HPP (qty terjual x harga beli master)
    modal_npk = qty_jual_npk * harga_npk.price_buy
    
    # 5. Hitung Biaya Operasional (status='SELESAI')
    biaya_armada = BiayaOperasional.filter(kategori='ARMADA', status='SELESAI').aggregate(Sum('nominal'))
    biaya_kantor = BiayaOperasional.filter(kategori='KANTOR', status='SELESAI').aggregate(Sum('nominal'))
    
    # 6. Hitung Laba
    gross_profit = total_omzet - total_modal
    net_profit = gross_profit - total_ops
    
    # 7. Neraca Singkat
    assets = cash_estimate + total_piutang + nilai_stok
    liabilities = biaya_status_proses  # belum dibayar
    equity = assets - liabilities
```

---

## 7. MODUL GUDANG - OPERASIONAL

### 7.1 Views & Functions

| View | URL | Fungsi |
|------|-----|--------|
| `so_list` | `/so/` | Daftar SO dengan virtual balance |
| `so_create` | `/so/create/` | Form input SO + alokasi kecamatan |
| `transfer_list` | `/transfer/` | Riwayat transfer |
| `transfer_create` | `/transfer/create/` | Form tarik stok ke gudang |
| `distribution_list` | `/distribution/` | Daftar surat jalan |
| `distribution_create` | `/distribution/create/` | Form buat surat jalan |
| `print_surat_jalan` | `/distribution/<pk>/print/` | Print surat jalan |
| `stock_card_list` | `/stock-card/` | Kartu stok dengan running balance |
| `stock_card_export_physical` | `/stock-card/export/` | Export PDF stok fisik |
| `stock_opname` | `/opname/` | Input penyesuaian stok |
| `order_note_list` | `/order-notes/` | Daftar catatan pesanan |
| `order_note_create` | `/order-notes/create/` | Form input pesanan |
| `order_note_complete` | `/order-notes/<pk>/complete/` | Tandai selesai |

### 7.2 Validasi Distribusi (validate_distribution_items)

```python
def validate_distribution_items(kios, dist_date, items_clean):
    so_balance = {}       # Track virtual balance per SO
    physical_balance = {} # Track physical balance per jenis
    quota_balance = {}    # Track kuota per jenis per tahun
    
    for item in items_clean:
        if item.source_type == 'VIRTUAL':
            # Cek stok virtual SO
            if so.id not in so_balance:
                so_balance[so.id] = so.get_virtual_balance()
            so_balance[so.id] -= item.tonnage
            if so_balance[so.id] < 0:
                raise ValidationError(f"Stok virtual SO tidak cukup")
        else:
            # Cek stok fisik
            if jenis.id not in physical_balance:
                physical_balance[jenis.id] = get_physical_stock(jenis)
            physical_balance[jenis.id] -= item.tonnage
            if physical_balance[jenis.id] < 0:
                raise ValidationError(f"Stok fisik tidak cukup")
        
        # Cek kuota kios
        qkey = (jenis.id, dist_date.year)
        if qkey not in quota_balance:
            alloc = KiosAllocation.get(kios, jenis, year)
            quota_balance[qkey] = alloc.quota_remaining
        quota_balance[qkey] -= item.tonnage
        if quota_balance[qkey] < 0:
            raise ValidationError(f"Kuota kios tidak cukup")
```

### 7.3 Stock Card Running Balance

```python
def stock_card_list(request):
    jenis_code = request.GET.get('jenis', 'NPK')
    stock_filter = request.GET.get('stock', 'PHYSICAL')
    
    jenis_pupuk = JenisPupuk.objects.filter(name__iexact=jenis_code).first()
    
    raw_cards = StockCard.objects.filter(
        jenis_pupuk=jenis_pupuk,
        stock_type=stock_filter
    ).order_by('date', 'created_at')
    
    # Hitung running balance
    saldo_akhir = 0
    cards = []
    for card in raw_cards:
        saldo_akhir += card.qty_in - card.qty_out
        card.current_balance = saldo_akhir
        cards.append(card)
    
    cards.reverse()  # Terbaru di atas
```

---

## 8. MODUL KEUANGAN - FINANCE

### 8.1 Views & Functions

| View | URL | Fungsi |
|------|-----|--------|
| `invoice_list` | `/invoice/` | Daftar invoice dengan total piutang |
| `payment_create` | `/invoice/<pk>/pay/` | Form input pembayaran |
| `print_invoice` | `/invoice/<pk>/print/` | Print invoice |
| `ops_list` | `/biaya/` | Daftar biaya operasional |
| `ops_create` | `/biaya/create/` | Form input biaya |
| `ops_approve` | `/biaya/<pk>/approve/` | Approve biaya (owner) |
| `ops_delete` | `/biaya/<pk>/delete/` | Hapus biaya |
| `kartu_kontrol_armada` | `/kartu-kontrol/` | Riwayat service per armada |
| `get_armada_history` | `/api/armada-history/` | API AJAX history armada |

### 8.2 Auto-Invoice Logic (Signal)

```python
@receiver(post_save, sender=Distribution)
def create_invoice_automatis(sender, instance, created, **kwargs):
    def _upsert_invoice(dist):
        # Hitung total dari items x harga master
        kab = dist.kios.kecamatan.kabupaten
        total = 0
        for item in dist.items.all():
            price = get_price_for(item.jenis_pupuk, kab)
            total += item.tonnage * price.price_sell
        
        # Create/Update invoice
        Invoice.objects.update_or_create(
            distribution=dist,
            defaults={
                'inv_number': dist.no_surat_jalan.replace('SJ', 'INV'),
                'issue_date': dist.date,
                'due_date': dist.date + timedelta(days=7),
                'total_amount': total,
            }
        )
    
    transaction.on_commit(lambda: _upsert_invoice(instance))
```

### 8.3 Payment Status Update Logic (Signal)

```python
@receiver(post_save, sender=Payment)
def update_invoice_status(sender, instance, created, **kwargs):
    invoice = instance.invoice
    
    # Hitung delta berdasarkan perubahan status
    if created and instance.status == 'APPROVED':
        delta = instance.amount
    elif old_status == 'APPROVED' and instance.status != 'APPROVED':
        delta = -instance.amount  # Rollback
    else:
        delta = 0
    
    if delta:
        invoice.total_paid += delta
        invoice.update_status()  # UNPAID → PARTIAL → PAID
```

---

## 9. MULTI-KABUPATEN ACCESS CONTROL

### 9.1 Konsep

- **Superuser:** Bisa akses semua data dari semua kabupaten
- **Staff/Admin:** Hanya bisa akses data dari kabupaten yang di-assign via `UserProfile.kabupaten`

### 9.2 Helper Functions (core/utils.py)

```python
def get_user_kabupaten(user):
    """Return kabupaten assigned to user (None for superuser)"""
    if user.is_superuser:
        return None
    return getattr(user.profile, 'kabupaten', None)

def get_scope_kabupaten(request):
    """
    Resolve kabupaten for current request:
    - Non-superuser: always user's kabupaten
    - Superuser: optional GET ?kabupaten=<id>
    """
    if not request.user.is_superuser:
        return get_user_kabupaten(request.user)
    
    kab_id = request.GET.get('kabupaten')
    if kab_id:
        return Kabupaten.objects.filter(pk=kab_id).first()
    return None

def scope_by_kabupaten(qs, user, kabupaten_field='kabupaten'):
    """
    Filter queryset by user's kabupaten.
    kabupaten_field: dotted lookup (e.g., 'kecamatan__kabupaten')
    """
    if user.is_superuser:
        return qs  # Tidak difilter
    
    kab = get_user_kabupaten(user)
    if not kab:
        return qs
    
    return qs.filter(**{kabupaten_field: kab})
```

### 9.3 Usage Example

```python
# Di views.py
@login_required
def kios_list(request):
    kios_data = Kios.objects.select_related('kecamatan__kabupaten')
    
    # Filter by kabupaten
    kios_data = scope_by_kabupaten(kios_data, request.user, 'kecamatan__kabupaten')
    
    return render(request, 'core/kios_list.html', {'kios_data': kios_data})

# Di template (untuk superuser dropdown)
{% if user.is_superuser %}
<form method="get">
    <select name="kabupaten">
        <option value="">Semua</option>
        {% for kab in kab_options %}
        <option value="{{ kab.id }}">{{ kab.name }}</option>
        {% endfor %}
    </select>
    <button type="submit">Filter</button>
</form>
{% endif %}
```

### 9.4 Tabel: Field Kabupaten Lookup per Model

| Model | Lookup Path |
|-------|-------------|
| Kios | `kecamatan__kabupaten` |
| SalesOrder | `allocations__kecamatan__kabupaten` |
| WarehouseTransfer | `source_so__allocations__kecamatan__kabupaten` |
| Distribution | `kios__kecamatan__kabupaten` |
| Invoice | `distribution__kios__kecamatan__kabupaten` |
| BiayaOperasional | `kabupaten` (direct FK) |
| OrderNote | `kecamatan__kabupaten` |

---

## 10. SIGNAL-DRIVEN AUTOMATION

### 10.1 Signal Registry

| App | Signal | Sender | Receiver | Fungsi |
|-----|--------|--------|----------|--------|
| core | post_save | User | ensure_user_profile | Auto-create UserProfile |
| gudang | post_save | SalesOrderAllocation | update_stock_from_allocation | Update StockCard VIRTUAL IN |
| gudang | post_delete | SalesOrderAllocation | update_stock_from_allocation | Rollback StockCard |
| gudang | post_save | WarehouseTransfer | update_stock_from_transfer | VIRTUAL OUT + PHYSICAL IN |
| gudang | post_delete | WarehouseTransfer | delete_stock_from_transfer | Rollback StockCard |
| gudang | pre_save | Distribution | cache_old_distribution | Simpan state lama |
| gudang | post_save | Distribution | update_stock_from_distribution | Legacy: single-item distribution |
| gudang | post_delete | Distribution | delete_stock_from_distribution | Rollback |
| gudang | pre_save | DistributionItem | cache_old_distribution_item | Simpan state lama |
| gudang | post_save | DistributionItem | update_stock_from_distribution_item | Update StockCard + Kuota |
| gudang | post_delete | DistributionItem | delete_stock_from_distribution_item | Rollback |
| keuangan | post_save | Distribution | create_invoice_automatis | Auto-create Invoice |
| keuangan | pre_save | Payment | stash_old_payment | Simpan state lama |
| keuangan | post_save | Payment | update_invoice_status | Update paid + status |
| keuangan | post_delete | Payment | rollback_invoice_status | Rollback paid + status |
| keuangan | post_save | DistributionItem | sync_invoice_on_item_save | Recalculate invoice |
| keuangan | post_delete | DistributionItem | sync_invoice_on_item_delete | Recalculate invoice |

### 10.2 StockCard Transaction Types

```
┌────────────────────────────────────────────────────────────────┐
│                    STOCKCARD TRANSACTION FLOW                   │
└────────────────────────────────────────────────────────────────┘

PENEBUSAN (SO):
└── IN_SO (VIRTUAL) ← qty_in = total alokasi

TRANSFER:
├── OUT_TRF (VIRTUAL) ← qty_out = tonnage
└── IN_TRF (PHYSICAL) ← qty_in = tonnage

DISTRIBUSI VIRTUAL:
├── OUT_DIST_V (VIRTUAL) ← qty_out = tonnage
├── IN_DIST_P (PHYSICAL) ← qty_in = tonnage (transit)
└── OUT_DIST_P (PHYSICAL) ← qty_out = tonnage (deliver)

DISTRIBUSI PHYSICAL:
└── OUT_DIST_P (PHYSICAL) ← qty_out = tonnage

OPNAME:
└── ADJUST (VIRTUAL/PHYSICAL) ← qty_in atau qty_out sesuai selisih
```

### 10.3 Helper: recompute_stock_balance

```python
def recompute_stock_balance(jenis_id, stock_type):
    """Re-calculate running balance untuk semua StockCard."""
    with transaction.atomic():
        cards = StockCard.objects.select_for_update().filter(
            jenis_pupuk_id=jenis_id,
            stock_type=stock_type
        ).order_by('date', 'created_at', 'id')
        
        running = Decimal('0')
        for card in cards:
            running += (card.qty_in or 0) - (card.qty_out or 0)
            if card.balance != running:
                StockCard.objects.filter(pk=card.pk).update(balance=running)
```

---

## 11. URL ROUTING & ENDPOINTS

### 11.1 Root URLs (sim_dp/urls.py)

```python
urlpatterns = [
    path('admin/', admin.site.urls),                    # Django Admin
    path('accounts/logout/', LogoutView, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', dashboard, name='dashboard'),              # Homepage
    path('', include('core.urls')),                     # Core routes
    path('', include('gudang.urls')),                   # Gudang routes
    path('', include('keuangan.urls')),                 # Keuangan routes
]
```

### 11.2 Core URLs

```
/kios/                          → kios_list
/kios/add/                      → kios_create
/kios/edit/<pk>/                → kios_update
/kios/delete/<pk>/              → kios_delete
/laporan/raport/                → raport_kios
/armada/                        → armada_list
/armada/add/                    → armada_create
/master/pupuk/                  → jenis_pupuk_list (redirect)
/master/pupuk/<pk>/edit/        → jenis_pupuk_edit (redirect)
/master/pupuk/<pk>/delete/      → jenis_pupuk_delete
/master/harga/                  → master_harga (redirect)
/master-data-pupuk/             → master_data_pupuk
/laporan/keuangan/              → laporan_keuangan
/setup/company-profile/         → setup_company_profile
/setup/kabupaten/               → setup_kabupaten
/setup/kabupaten/<pk>/edit/     → setup_kabupaten_edit
/setup/kabupaten/<pk>/delete/   → setup_kabupaten_delete
/setup/kecamatan/               → setup_kecamatan
/setup/kecamatan/<pk>/edit/     → setup_kecamatan_edit
/setup/kecamatan/<pk>/delete/   → setup_kecamatan_delete
/setup/users/                   → setup_users
/setup/users/<id>/password/     → setup_user_set_password
```

### 11.3 Gudang URLs

```
/so/                            → so_list
/so/create/                     → so_create
/transfer/                      → transfer_list
/transfer/create/               → transfer_create
/distribution/                  → distribution_list
/distribution/create/           → distribution_create
/distribution/<pk>/print/       → print_surat_jalan
/stock-card/                    → stock_card_list
/stock-card/export/             → stock_card_export_physical
/opname/                        → stock_opname
/order-notes/                   → order_note_list
/order-notes/create/            → order_note_create
/order-notes/<pk>/complete/     → order_note_complete
```

### 11.4 Keuangan URLs

```
/invoice/                       → invoice_list
/invoice/<pk>/pay/              → payment_create
/invoice/<pk>/print/            → print_invoice
/biaya/                         → ops_list
/biaya/create/                  → ops_create
/biaya/<pk>/approve/            → ops_approve
/biaya/<pk>/delete/             → ops_delete
/kartu-kontrol/                 → kartu_kontrol_armada
/api/armada-history/            → get_armada_history (AJAX)
```

---

## 12. TEMPLATE STRUCTURE

### 12.1 Base Template (templates/base.html)

```html
<!DOCTYPE html>
<html>
<head>
    <!-- Bootstrap 5.3, Poppins Font, Bootstrap Icons -->
    <!-- Custom CSS: static/css/app.css -->
</head>
<body>
    <!-- Sidebar Overlay (mobile) -->
    <div class="sidebar-overlay"></div>
    
    <!-- Sidebar -->
    <div class="sidebar">
        <div class="sidebar-brand">SIM-DP</div>
        <nav>
            <!-- Dashboard -->
            <!-- Section: Gudang (collapsible) -->
            <!-- Section: Master Data (collapsible) -->
            <!-- Section: Setup (staff only) -->
            <!-- Section: Keuangan & Ops (collapsible) -->
        </nav>
        <div class="sidebar-footer">
            <form action="{% url 'logout' %}" method="post">
                <button>Logout</button>
            </form>
        </div>
    </div>
    
    <!-- Main Content -->
    <div class="main">
        <div class="topbar">
            <!-- Page title, date, user info -->
        </div>
        
        <!-- Flash Messages -->
        {% if messages %}
        <div class="container-fluid">
            {% for message in messages %}
            <div class="alert alert-{{ message.tags }}">{{ message }}</div>
            {% endfor %}
        </div>
        {% endif %}
        
        <!-- Page Content -->
        {% block content %}{% endblock %}
    </div>
    
    <!-- Bootstrap JS, Custom JS: static/js/layout.js -->
    <!-- Currency formatting script -->
</body>
</html>
```

### 12.2 Template Naming Convention

```
templates/
├── base.html                   # Layout utama
├── dashboard.html              # Dashboard (extends base.html)
│
├── core/
│   ├── kios_list.html          # List view
│   ├── kios_form.html          # Create/Edit form
│   ├── kios_confirm_delete.html
│   ├── laporan_keuangan.html   # Report view
│   └── master_data_pupuk.html  # Combined CRUD
│
├── gudang/
│   ├── so_list.html
│   ├── so_form.html
│   ├── distribution_form.html  # Complex multi-item form
│   ├── print_surat_jalan.html  # Print layout (standalone)
│   └── stock_card_list.html
│
├── keuangan/
│   ├── invoice_list.html
│   ├── payment_form.html
│   ├── ops_list.html
│   ├── ops_form.html
│   └── print_invoice.html      # Print layout (standalone)
│
├── setup/
│   ├── company_profile.html
│   ├── kabupaten_list.html
│   ├── kecamatan_list.html
│   └── user_list.html
│
└── registration/
    └── login.html              # Login page (standalone)
```

### 12.3 CSS Classes (static/css/app.css)

```css
/* Layout */
.sidebar { ... }                /* Sidebar navigation */
.sidebar.collapsed { ... }      /* Collapsed state */
.main { ... }                   /* Main content area */
.topbar { ... }                 /* Top navigation bar */

/* Navigation */
.nav-link { ... }               /* Sidebar links */
.nav-link.active { ... }        /* Active state */
.nav-section-toggle { ... }     /* Collapsible section */
.submenu { ... }                /* Dropdown menu */

/* Tables */
.table-sim { ... }              /* Custom table style */
.table-sim-wrapper { ... }      /* Responsive wrapper */

/* Forms */
.currency-input { ... }         /* Number formatting */

/* Badges & Status */
.status-badge.active { ... }
.status-badge.inactive { ... }
.fertilizer-badge.npk { ... }
.fertilizer-badge.urea { ... }
```

---

## 13. VALIDASI & BUSINESS RULES

### 13.1 Master Data Rules

| Rule | Implementasi |
|------|--------------|
| Harga pupuk > 0 | Form validation di `HargaPupukForm.clean()` |
| Kabupaten unik | Model constraint `unique=True` |
| Kecamatan unik | Model constraint `unique=True` |
| Tidak bisa hapus kabupaten jika ada kecamatan | View check `kab.kecamatan_list.exists()` |
| Tidak bisa hapus kecamatan jika ada kios | View check `kec.kios_list.exists()` |
| Jenis pupuk tidak bisa dihapus jika terpakai | Auto-archive (is_active=False) |

### 13.2 Transaksi Rules

| Rule | Implementasi |
|------|--------------|
| Stok virtual cukup untuk transfer | `WarehouseTransfer.clean()` |
| Stok virtual/fisik cukup untuk distribusi | `validate_distribution_items()` |
| Kuota kios cukup untuk distribusi | `validate_distribution_items()` |
| Pembayaran ≤ sisa tagihan | `Payment.clean()` dan `PaymentForm.clean_amount()` |
| SO auto-close jika saldo habis | Signal `update_so_closure()` |

### 13.3 Access Control Rules

| Rule | Implementasi |
|------|--------------|
| Staff hanya akses kabupaten sendiri | `scope_by_kabupaten()` di views |
| Hanya staff akses Setup pages | `@user_passes_test(lambda u: u.is_staff)` |
| Hanya Owner approve biaya | `@owner_required` decorator |
| Laporan keuangan perlu pilih kabupaten | Check di `laporan_keuangan()` view |

### 13.4 Data Integrity Rules

| Rule | Implementasi |
|------|--------------|
| Atomic transactions | `with transaction.atomic():` |
| StockCard adalah single source of truth | Semua perubahan via signals |
| Invoice auto-update saat payment berubah | Signals di keuangan |
| Kuota kios auto-update saat distribusi | Signals di gudang |

---

## 14. DEPLOYMENT & CONFIGURATION

### 14.1 Environment Variables (.env)

```bash
# WAJIB - Security
SECRET_KEY=isi_kunci_acak_panjang_dan_unik
DEBUG=False
ALLOWED_HOSTS=pupuk.sie.web.id,127.0.0.1

# WAJIB - Database
DB_NAME=simdp_db
DB_USER=simdp_user
DB_PASSWORD=secure_password_here
DB_HOST=localhost
DB_PORT=5432

# WAJIB (Production) - CSRF Origins
CSRF_TRUSTED_ORIGINS=https://pupuk.sie.web.id

# OPSIONAL - Cookie Security (default: True)
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_SAMESITE=Lax

# OPSIONAL - Cloudflare R2 Storage
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket
R2_ENDPOINT_URL=https://xxx.r2.cloudflarestorage.com

# OPSIONAL - Gunicorn
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=120
```

### 14.2 Dockerfile

```dockerfile
FROM python:3.11-slim

# System dependencies (untuk PDF rendering)
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev libcairo2-dev \
    libpango1.0-dev libgdk-pixbuf-2.0-0

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project
COPY . /app
WORKDIR /app

EXPOSE 8000

# Entrypoint: migrate → collectstatic → gunicorn
ENTRYPOINT ["/bin/sh", "-c", "\
    python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    gunicorn sim_dp.wsgi:application --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} --timeout ${GUNICORN_TIMEOUT:-120}"]
```

### 14.3 Deployment Checklist

```
□ 1. Setup DNS A record ke IP server
□ 2. Buat PostgreSQL database di Coolify
□ 3. Create Application dari Git repo
□ 4. Set Environment Variables (lihat 14.1)
□ 5. Add Volume untuk /app/media
□ 6. Deploy & tunggu status Running
□ 7. Enable HTTPS/SSL via Let's Encrypt
□ 8. Exec ke container: python manage.py createsuperuser
□ 9. Login & setup master data:
   □ a. Company Profile
   □ b. Kabupaten
   □ c. Kecamatan
   □ d. Jenis Pupuk + Harga (per kabupaten)
   □ e. Armada
   □ f. User (assign kabupaten)
   □ g. Kios + Alokasi
```

---

## 15. TROUBLESHOOTING GUIDE

### 15.1 Common Errors

| Error | Penyebab | Solusi |
|-------|----------|--------|
| "Harga pupuk belum dikonfigurasi" | Harga belum diset untuk kabupaten | Set harga di Master Data Pupuk |
| "Harga pupuk harus lebih dari 0" | Harga beli/jual = 0 | Update harga > 0 |
| "Stok virtual tidak cukup" | Saldo SO habis | Cek kartu stok, mungkin perlu SO baru |
| "Stok fisik tidak cukup" | Belum ada transfer | Tarik stok dari SO ke gudang |
| "Kuota kios tidak cukup" | Alokasi habis | Update alokasi di data kios |
| "Jumlah melebihi sisa tagihan" | Payment > remaining | Input amount ≤ sisa |
| 403 Forbidden di Setup | User bukan staff | Set is_staff=True di admin |
| Data tidak muncul | Filter kabupaten salah | Superuser: pilih kabupaten; Staff: auto-filter |

### 15.2 Debug Commands

```bash
# Masuk ke container
docker exec -it <container_name> sh

# Django shell
python manage.py shell

# Check StockCard balance
from gudang.models import StockCard
from django.db.models import Sum
StockCard.objects.filter(jenis_pupuk__name='NPK', stock_type='VIRTUAL') \
    .aggregate(saldo=Sum('qty_in')-Sum('qty_out'))

# Check Invoice status
from keuangan.models import Invoice
Invoice.objects.filter(status='UNPAID').count()

# Recompute stock balance
from gudang.signals import recompute_stock_balance
from core.models import JenisPupuk
npk = JenisPupuk.objects.get(code='NPK')
recompute_stock_balance(npk.id, 'VIRTUAL')
recompute_stock_balance(npk.id, 'PHYSICAL')

# Force update SO closure
from gudang.signals import update_so_closure
from gudang.models import SalesOrder
for so in SalesOrder.objects.filter(is_closed=False):
    update_so_closure(so)
```

### 15.3 Log Locations

```
# Django errors (development)
Terminal output

# Gunicorn errors (production)
docker logs <container_name>

# Database errors
Check Coolify PostgreSQL service logs
```

---

## 📝 CATATAN PENUTUP

### Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    SIM-DP QUICK REFERENCE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  STOK VIRTUAL (Pabrik)                                          │
│  └── Bertambah: Penebusan SO (IN_SO)                            │
│  └── Berkurang: Transfer (OUT_TRF), Distribusi Virtual (OUT_DIST_V)│
│                                                                  │
│  STOK FISIK (Gudang)                                            │
│  └── Bertambah: Transfer (IN_TRF), Transit Distribusi (IN_DIST_P)│
│  └── Berkurang: Distribusi (OUT_DIST_P)                         │
│                                                                  │
│  INVOICE                                                         │
│  └── Auto-create saat Distribusi                                │
│  └── Status: UNPAID → PARTIAL → PAID                            │
│  └── Due date: issue_date + 7 hari                              │
│                                                                  │
│  BIAYA OPERASIONAL                                              │
│  └── Status: PROSES → SELESAI (perlu approval)                  │
│  └── SELESAI masuk Laporan Laba Rugi                            │
│  └── PROSES dianggap liabilitas (hutang)                        │
│                                                                  │
│  ACCESS CONTROL                                                  │
│  └── Superuser: semua data, filter dropdown                     │
│  └── Staff/Admin: scoped ke kabupaten yang di-assign            │
│                                                                  │
│  SINGLE SOURCE OF TRUTH                                          │
│  └── StockCard = Kartu Stok = Ledger                            │
│  └── Semua perubahan stok via Django Signals                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Kontak & Support

```
Repository  : github.com/mrraihan29/project_pupuk
Branch      : main
Framework   : Django 5.0
Database    : PostgreSQL
```

---

**Dokumen ini dibuat untuk membantu developer memahami project SIM-DP secara komprehensif. Jika ada pertanyaan atau butuh klarifikasi, silakan buka issue di repository.**

---

*Last Updated: Februari 2026*
