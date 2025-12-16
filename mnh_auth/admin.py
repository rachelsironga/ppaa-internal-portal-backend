from django.contrib import admin

from mnh_auth.models import User, Country, Currency


class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'email']


class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'iso_code', 'slug', 'is_deleted']
    search_fields = ['name', 'iso_code']
    list_filter = ['is_deleted', 'created_at']
    readonly_fields = ['slug', 'uid', 'created_at', 'updated_at']


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_deleted']
    search_fields = ['name', 'code']
    list_filter = ['is_deleted', 'created_at']
    readonly_fields = ['uid', 'created_at', 'updated_at']


admin.site.register(User, UserAdmin)
admin.site.register(Country, CountryAdmin)
admin.site.register(Currency, CurrencyAdmin)