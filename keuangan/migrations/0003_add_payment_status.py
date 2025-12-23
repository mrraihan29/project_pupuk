from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('keuangan', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(choices=[('APPROVED', 'Disetujui'), ('PENDING', 'Menunggu'), ('VOID', 'Void / Batal')], default='APPROVED', max_length=10),
        ),
    ]
