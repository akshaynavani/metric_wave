import django.db.models.deletion
from django.db import migrations, models

import metrics.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Dashboard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                ("api_key", models.CharField(default=metrics.models.generate_api_key, max_length=64, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["slug"]},
        ),
        migrations.CreateModel(
            name="MetricPoint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                ("value", models.FloatField()),
                ("timestamp", models.DateTimeField(db_index=True)),
                ("tags", models.JSONField(blank=True, default=dict)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="points", to="metrics.source")),
            ],
            options={
                "ordering": ["-timestamp"],
                "indexes": [models.Index(fields=["source", "name", "-timestamp"], name="point_src_name_ts")],
            },
        ),
        migrations.CreateModel(
            name="Widget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=128)),
                ("kind", models.CharField(choices=[("line", "Line chart"), ("stat", "Single stat"), ("bar", "Bar chart")], default="line", max_length=8)),
                ("metric_name", models.CharField(max_length=128)),
                ("aggregation", models.CharField(choices=[("avg", "Average"), ("sum", "Sum"), ("min", "Minimum"), ("max", "Maximum"), ("count", "Count")], default="avg", max_length=8)),
                ("window_minutes", models.PositiveIntegerField(default=15)),
                ("bucket_seconds", models.PositiveIntegerField(default=10)),
                ("position", models.PositiveIntegerField(default=0)),
                ("dashboard", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="widgets", to="metrics.dashboard")),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="widgets", to="metrics.source")),
            ],
            options={"ordering": ["dashboard", "position", "id"]},
        ),
    ]
