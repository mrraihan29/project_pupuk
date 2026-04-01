from decimal import Decimal

from django.db import migrations


def fix_transfer_virtual_out_ledger(apps, schema_editor):
    StockCard = apps.get_model('gudang', 'StockCard')

    # Heal historis transfer virtual: OUT_TRF sempat tersimpan sebagai qty_in.
    broken_cards = StockCard.objects.filter(
        stock_type='VIRTUAL',
        transaction_type='OUT_TRF',
    ).exclude(qty_in=Decimal('0'))

    for card in broken_cards.iterator():
        moved_in = card.qty_in or Decimal('0')
        if moved_in == 0:
            continue
        card.qty_out = (card.qty_out or Decimal('0')) + moved_in
        card.qty_in = Decimal('0')
        card.save(update_fields=['qty_in', 'qty_out'])

    # Recompute running balance virtual per jenis agar field balance kembali konsisten.
    jenis_ids = StockCard.objects.filter(stock_type='VIRTUAL').values_list('jenis_pupuk_id', flat=True).distinct()
    for jenis_id in jenis_ids:
        running = Decimal('0')
        rows = StockCard.objects.filter(
            jenis_pupuk_id=jenis_id,
            stock_type='VIRTUAL',
        ).order_by('date', 'created_at', 'id')

        for row in rows.iterator():
            running += (row.qty_in or Decimal('0')) - (row.qty_out or Decimal('0'))
            if row.balance != running:
                row.balance = running
                row.save(update_fields=['balance'])


def noop_reverse(apps, schema_editor):
    # Perbaikan data historis tidak dibalik agar ledger tetap benar.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gudang', '0012_alter_distribution_source_type_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_transfer_virtual_out_ledger, noop_reverse),
    ]
