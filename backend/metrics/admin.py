from django.contrib import admin

from .models import Dashboard, MetricPoint, Source, Widget


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "is_active", "created_at")
    search_fields = ("slug", "name")
    readonly_fields = ("api_key", "created_at")


@admin.register(MetricPoint)
class MetricPointAdmin(admin.ModelAdmin):
    list_display = ("source", "name", "value", "timestamp")
    list_filter = ("source", "name")
    date_hierarchy = "timestamp"


class WidgetInline(admin.TabularInline):
    model = Widget
    extra = 0


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "updated_at")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [WidgetInline]
