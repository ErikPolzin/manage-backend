# Generated by Django 5.0 on 2024-06-25 08:48

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=100, unique=True)),
                ('name', models.CharField(max_length=20, unique=True)),
                ('service_type', models.CharField(choices=[('utility', 'utility'), ('entertainment', 'entertainment'), ('games', 'games'), ('education', 'education')], max_length=20)),
                ('api_location', models.CharField(choices=[('cloud', 'cloud'), ('local', 'local')], max_length=10)),
            ],
        ),
    ]
