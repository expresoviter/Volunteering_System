from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_verified', 'created_by', 'member_count', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'created_by')
    actions = ['verify_organizations']

    def member_count(self, obj):
        return obj.members.filter(role='coordinator').count()
    member_count.short_description = 'Координатори'

    @admin.action(description='Верифікувати вибрані організації (та всіх їхніх координаторів)')
    def verify_organizations(self, request, queryset):
        for org in queryset:
            org.is_verified = True
            org.save()
        self.message_user(request, f"{queryset.count()} організацію(й) верифіковано.")


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'organization', 'is_verified', 'is_active', 'deleted_at', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_active', 'is_staff')
    list_editable = ('is_verified',)
    readonly_fields = ('deleted_at',)
    fieldsets = UserAdmin.fieldsets + (
        ('Роль та організація', {'fields': ('role', 'organization', 'is_verified')}),
        ('Видалення', {'fields': ('deleted_at',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Роль та організація', {'fields': ('role', 'organization', 'is_verified')}),
    )
    actions = ['verify_coordinators', 'restore_accounts']

    def get_queryset(self, request):
        # Показуємо всіх користувачів, включно з «м'яко видаленими», в адмінці
        return super().get_queryset(request)

    @admin.action(description='Верифікувати вибраних координаторів')
    def verify_coordinators(self, request, queryset):
        updated = queryset.filter(role='coordinator').update(is_verified=True)
        self.message_user(request, f"{updated} координатора(ів) верифіковано.")

    @admin.action(description='Відновити вибрані видалені акаунти')
    def restore_accounts(self, request, queryset):
        updated = queryset.update(is_active=True, deleted_at=None)
        self.message_user(request, f"{updated} акаунт(ів) відновлено.")
