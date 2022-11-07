# Generated by Django 4.0.6 on 2022-11-01 22:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='processingjob',
            name='case',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='portal.case'),
        ),
        migrations.AlterField(
            model_name='processingjob',
            name='dicom_set',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='portal.dicomset'),
        ),
        migrations.AlterField(
            model_name='processingjob',
            name='docker_image',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]