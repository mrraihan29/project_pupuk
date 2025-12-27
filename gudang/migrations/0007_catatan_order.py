from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('gudang', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Tanggal Order')),
                ('notes', models.TextField(blank=True, verbose_name='Catatan')),
                ('status', models.CharField(choices=[('OPEN', 'Terbuka'), ('DONE', 'Selesai')], default='OPEN', max_length=10, verbose_name='Status')),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('kecamatan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.kecamatan', verbose_name='Kecamatan')),
                ('kios', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.kios', verbose_name='Kios')),
            ],
            options={
                'verbose_name': 'Catatan Order',
                'verbose_name_plural': 'Catatan Order',
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='OrderNoteItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tonnage', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Jumlah (Ton)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('jenis_pupuk', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.jenispupuk', verbose_name='Jenis Pupuk')),
                ('linked_distribution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_note_items', to='gudang.distribution')),
                ('linked_sales_order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_note_items', to='gudang.salesorder')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='gudang.ordernote')),
            ],
            options={
                'verbose_name': 'Item Catatan Order',
                'verbose_name_plural': 'Item Catatan Order',
            },
        ),
    ]
