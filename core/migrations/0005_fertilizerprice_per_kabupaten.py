from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    FertilizerPrice = apps.get_model('core', 'FertilizerPrice')
    for price in FertilizerPrice.objects.all():
        price.kabupaten = None
        price.save(update_fields=['kabupaten'])


def reverse(apps, schema_editor):
    # No-op rollback
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_remove_kecamatan_target_tonnage'),
    ]

    operations = [
        migrations.AddField(
            model_name='fertilizerprice',
            name='kabupaten',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='fertilizer_prices', to='core.kabupaten'),
        ),
        migrations.AlterField(
            model_name='fertilizerprice',
            name='jenis_pupuk',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.jenispupuk', verbose_name='Jenis Pupuk'),
        ),
        migrations.RunPython(forwards, reverse_code=reverse),
        migrations.AlterUniqueTogether(
            name='fertilizerprice',
            unique_together={('jenis_pupuk', 'kabupaten')},
        ),
    ]
