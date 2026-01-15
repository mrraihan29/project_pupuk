from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gudang', '0008_distributionitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='distributionitem',
            name='order_item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deliveries', to='gudang.ordernoteitem'),
        ),
    ]
