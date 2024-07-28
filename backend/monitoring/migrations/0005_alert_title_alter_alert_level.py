# Generated by Django 5.0.6 on 2024-07-28 09:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0004_node_health_status_alter_alert_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='alert',
            name='title',
            field=models.CharField(default='NoTitle', max_length=100),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='alert',
            name='level',
            field=models.SmallIntegerField(choices=[(1, 'Warning'), (2, 'ERROR'), (3, 'Critical')]),
        ),
    ]
