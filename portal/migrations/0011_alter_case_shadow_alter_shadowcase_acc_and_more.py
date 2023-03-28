# Generated by Django 4.0.6 on 2023-03-15 16:11

from django.db import migrations, models
import django.db.models.deletion
import portal.models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0010_shadowcase_alter_case_tags_alter_userprofile_user_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='shadow',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cases', to='portal.shadowcase'),
        ),
        migrations.AlterField(
            model_name='shadowcase',
            name='acc',
            field=models.CharField(default=portal.models.ShadowCase.default_num_a, max_length=20),
        ),
        migrations.AlterField(
            model_name='shadowcase',
            name='mrn',
            field=models.CharField(default=portal.models.ShadowCase.default_num_m, max_length=20),
        ),
    ]