from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0003_alter_processingjob_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='processingjob',
            name='case',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='portal.case'),
        ),
        migrations.AddField(
            model_name='processingjob',
            name='parameters',
            field=models.JSONField(null=True),
        ),
        migrations.AlterField(
            model_name='dicominstance',
            name='dicom_set',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instances', to='portal.dicomset'),
        ),
        migrations.AlterField(
            model_name='dicomset',
            name='case',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dicom_sets', to='portal.case'),
        ),
        migrations.AlterField(
            model_name='dicomset',
            name='processing_result',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='result_sets', to='portal.processingjob'),
        ),
    ]
