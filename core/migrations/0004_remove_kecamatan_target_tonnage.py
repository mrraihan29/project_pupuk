from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_kabupaten_alter_fertilizerprice_price_buy_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='kecamatan',
            name='target_tonnage',
        ),
    ]
