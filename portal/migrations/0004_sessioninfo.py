# Generated by Django 4.0.6 on 2022-12-05 21:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0003_alter_case_case_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='SessionInfo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_stored', models.DateTimeField(default=django.utils.timezone.now)),
                ('view_state', models.JSONField()),
                ('current_session_tag', models.CharField(blank=True, max_length=100, null=True)),
                ('case', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='portal.case')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'gravis_session',
            },
        ),
    ]
