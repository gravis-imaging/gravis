# Generated by Django 4.0.6 on 2022-08-03 21:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0002_imagejob_complete'),
    ]

    operations = [
        migrations.CreateModel(
            name='DockerJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('docker_image', models.CharField(max_length=10000)),
                ('input_folder', models.CharField(max_length=10000)),
                ('output_folder', models.CharField(max_length=10000)),
                ('complete', models.BooleanField(default=False)),
            ],
        ),
    ]