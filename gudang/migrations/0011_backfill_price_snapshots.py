"""
Data migration: Backfill price_sell_snapshot & price_buy_snapshot
pada DistributionItem yang sudah ada menggunakan harga master saat ini.

Ini hanya berjalan sekali. Setelah ini, semua item baru akan otomatis
mendapatkan price snapshot dari signal pre_save.
"""
from django.db import migrations
from decimal import Decimal


def backfill_prices(apps, schema_editor):
    DistributionItem = apps.get_model('gudang', 'DistributionItem')
    FertilizerPrice = apps.get_model('core', 'FertilizerPrice')

    items = DistributionItem.objects.filter(
        price_sell_snapshot__isnull=True
    ).select_related(
        'jenis_pupuk',
        'distribution__kios__kecamatan__kabupaten'
    )

    for item in items.iterator():
        kab = None
        try:
            kab = item.distribution.kios.kecamatan.kabupaten
        except AttributeError:
            pass

        price = None
        if kab:
            price = FertilizerPrice.objects.filter(
                jenis_pupuk=item.jenis_pupuk,
                kabupaten=kab
            ).first()
        if not price:
            price = FertilizerPrice.objects.filter(
                jenis_pupuk=item.jenis_pupuk
            ).first()

        if price:
            item.price_sell_snapshot = price.price_sell
            item.price_buy_snapshot = price.price_buy
            item.save(update_fields=['price_sell_snapshot', 'price_buy_snapshot'])


def noop(apps, schema_editor):
    """Reverse migration: no-op (snapshot data masih aman)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gudang', '0010_add_price_snapshots_to_distributionitem'),
        ('core', '0008_add_bank_account_name'),
    ]

    operations = [
        migrations.RunPython(backfill_prices, noop),
    ]
