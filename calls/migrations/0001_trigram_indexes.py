from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # Таблица calls уже существует (managed=False) — операция только для state Django.
        migrations.CreateModel(
            name='Call',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('from_ip', models.CharField(blank=True, max_length=45, null=True)),
                ('to_ip', models.CharField(blank=True, max_length=45, null=True)),
                ('call_id', models.CharField(blank=True, max_length=64, null=True)),
                ('from_number', models.CharField(blank=True, max_length=32, null=True)),
                ('to_number', models.CharField(blank=True, max_length=32, null=True)),
                ('calling_date', models.DateField(blank=True, null=True)),
                ('calling_time', models.TimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'calls',
                'ordering': ['-calling_date', '-calling_time', '-id'],
                'managed': False,
            },
        ),
        # GIN-индексы pg_trgm ускоряют LIKE/ILIKE с % в любой позиции
        # (маски вида x*, *x, *x*); точное совпадение обслуживают
        # существующие B-tree индексы.
        migrations.RunSQL(
            sql=[
                'CREATE EXTENSION IF NOT EXISTS pg_trgm;',
                'CREATE INDEX IF NOT EXISTS idx_calls_call_id_trgm '
                'ON calls USING gin (call_id gin_trgm_ops);',
                'CREATE INDEX IF NOT EXISTS idx_calls_from_number_trgm '
                'ON calls USING gin (from_number gin_trgm_ops);',
                'CREATE INDEX IF NOT EXISTS idx_calls_to_number_trgm '
                'ON calls USING gin (to_number gin_trgm_ops);',
            ],
            reverse_sql=[
                'DROP INDEX IF EXISTS idx_calls_call_id_trgm;',
                'DROP INDEX IF EXISTS idx_calls_from_number_trgm;',
                'DROP INDEX IF EXISTS idx_calls_to_number_trgm;',
            ],
        ),
    ]
