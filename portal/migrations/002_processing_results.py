from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='processingresult',
            name='case',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='portal.case'),
        ),
        migrations.AddField(
            model_name='processingresult',
            name='parameters',
            field=models.JSONField(null=True),
        ),
        migrations.RemoveConstraint(
            model_name='processingresult',
            name='both_dicom_set_and_json_result_cannot_be_null',
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
    ]
