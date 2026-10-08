from django.contrib import admin

from .models import (
    Expense, ExpenseSplit, Group, GroupInvite, GroupMembership, Member,
    MilkEntry, MilkPayment, MilkVendor, UserSettings,
)


@admin.register(MilkVendor)
class MilkVendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'price_per_litre']


@admin.register(MilkEntry)
class MilkEntryAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'litres', 'payment', 'created_at']
    list_filter = ['vendor']


@admin.register(MilkPayment)
class MilkPaymentAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'total_litres', 'amount', 'paid_at']


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
    list_display = ['name', 'owner', 'user', 'created_at']
    list_filter = ['owner']


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['group', 'user', 'member', 'role', 'joined_at']
    list_filter = ['role']


@admin.register(GroupInvite)
class GroupInviteAdmin(admin.ModelAdmin):
    list_display = ['group', 'code', 'created_at']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'group', 'amount', 'paid_by', 'created_at']
    list_filter = ['group']
    inlines = [ExpenseSplitInline]
