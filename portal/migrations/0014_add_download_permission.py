from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0013_remove_dicominstance_gravis_dico_dicom_s_1260e0_idx_and_more"),
    ]
    operations = [
        migrations.AlterModelOptions(
            name="case",
            options={
                "permissions": [
                    ("reprocess", "Can reprocess cases"),
                    ("rotate", "Can rotate cases"),
                    ("download", "Can download cases"),
                ]
            },
        ),
    ]
