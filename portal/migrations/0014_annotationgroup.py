import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0013_remove_dicominstance_gravis_dico_dicom_s_1260e0_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnotationGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=200)),
                ('annotations', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('cases', models.ManyToManyField(blank=True, related_name='annotation_groups', to='portal.case')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'gravis_annotation_group',
            },
        ),
        migrations.AddField(
            model_name='sessioninfo',
            name='annotation_group',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sessions',
                to='portal.annotationgroup',
            ),
        ),
    ]
