from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


def migrate_distribution_items(apps, schema_editor):
    Distribution = apps.get_model('gudang', 'Distribution')
    DistributionItem = apps.get_model('gudang', 'DistributionItem')
    for dist in Distribution.objects.all():
        DistributionItem.objects.create(
            distribution=dist,
            jenis_pupuk=dist.jenis_pupuk,
            source_type=dist.source_type,
            source_so=dist.source_so,
            tonnage=dist.tonnage,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('gudang', '0007_distributionitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='DistributionItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_type', models.CharField(choices=[('VIRTUAL', 'Langsung dari Pabrik (Potong SO)'), ('PHYSICAL', 'Dari Gudang Penyangga (Potong Stok Fisik)')], default='VIRTUAL', max_length=10, verbose_name='Sumber Stok')),
                ('tonnage', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Jumlah Kirim (Ton)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('distribution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='gudang.distribution')),
                ('jenis_pupuk', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.jenispupuk', verbose_name='Jenis Pupuk')),
                ('source_so', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='distribution_items', to='gudang.salesorder', verbose_name='Ambil dari SO')),
            ],
            options={
                'verbose_name': 'Detail Distribusi',
                'verbose_name_plural': 'Detail Distribusi',
            },
        ),
        migrations.RunPython(code=migrate_distribution_items, reverse_code=migrations.RunPython.noop),
    ]
