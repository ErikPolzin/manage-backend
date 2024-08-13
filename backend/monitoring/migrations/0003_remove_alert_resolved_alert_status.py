# Generated by Django 5.0.7 on 2024-08-10 16:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0002_alert_modified'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='alert',
            name='resolved',
        ),
        migrations.AddField(
            model_name='alert',
            name='status',
            field=models.SmallIntegerField(choices=[(1, 'New'), (2, 'Upgraded'), (3, 'Rename'), (4, 'Resolved')], default=1),
        ),
    ]