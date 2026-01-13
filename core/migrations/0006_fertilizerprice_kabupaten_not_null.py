from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    FertilizerPrice = apps.get_model('core', 'FertilizerPrice')
    Kabupaten = apps.get_model('core', 'Kabupaten')
    kab = Kabupaten.objects.first()
    if kab is None:
        kab = Kabupaten.objects.create(name='DEFAULT', code='DEF', is_active=True)
    null_prices = list(FertilizerPrice.objects.filter(kabupaten__isnull=True))
    for price in null_prices:
        # Jika sudah ada record untuk kombinasi ini, hapus duplikat null
        if FertilizerPrice.objects.filter(jenis_pupuk=price.jenis_pupuk, kabupaten=kab).exists():
            price.delete()
        else:
            price.kabupaten = kab
            price.save(update_fields=['kabupaten'])


def reverse(apps, schema_editor):
    # No-op; field will stay non-nullable
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_fertilizerprice_per_kabupaten'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=reverse),
        migrations.AlterField(
            model_name='fertilizerprice',
            name='kabupaten',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='fertilizer_prices', to='core.kabupaten'),
        ),
    ]
