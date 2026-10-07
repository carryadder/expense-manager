from django.contrib import admin

from .models import Expense, ExpenseSplit, Group, Member, UserSettings


class ExpenseSplitInline(admin.TabularInline):
    model = ExpenseSplit
    extra = 0


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'icon', 'created_at']
    list_filter = ['owner']


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'display_name', 'currency', 'date_format']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_at']
    list_filter = ['owner']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'group', 'amount', 'paid_by', 'created_at']
    list_filter = ['group']
    inlines = [ExpenseSplitInline]
