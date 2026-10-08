from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    ExpenseForm, GroupForm, InviteUserForm, MemberForm, MilkEntryForm,
    MilkVendorForm, SettingsForm, SignUpForm,
)
from .icons import GROUP_ICON_CHOICES
from .models import (
    Expense, Group, GroupInvite, GroupMembership, Member, MilkEntry,
    MilkPayment, MilkVendor, UserSettings,
)


def _group_for_member(request, pk):
    """Fetch a group the current user is a member of, or 404."""
    group = get_object_or_404(Group, pk=pk)
    if not group.is_member(request.user):
        from django.http import Http404
        raise Http404('Not a member of this group.')
    return group


def signup(request):
    if request.user.is_authenticated:
        return redirect('group_list')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Welcome! Create your first group to get started.')
            return redirect('group_list')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def group_list(request):
    group_ids = GroupMembership.objects.filter(
        user=request.user).values_list('group_id', flat=True)
    groups = Group.objects.filter(id__in=group_ids)
    grand_total = groups.aggregate(s=Sum('expenses__amount'))['s'] or Decimal('0.00')
    return render(request, 'expenses/group_list.html', {
        'groups': groups,
        'grand_total': grand_total,
        'member_count': Member.objects.filter(owner=request.user, user__isnull=True).count(),
    })


@login_required
def group_create(request):
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.owner = request.user
            if group.icon not in GROUP_ICON_CHOICES:
                group.icon = 'wallet'
            group.save()
            # Creator becomes the admin member of their own group.
            GroupMembership.add_user(group, request.user, role=GroupMembership.ADMIN)
            messages.success(request, f'Group "{group.name}" created.')
            return redirect('group_detail', pk=group.pk)
    else:
        form = GroupForm()
    return render(request, 'expenses/group_form.html', {
        'form': form,
        'icon_choices': GROUP_ICON_CHOICES,
    })


@login_required
def settings_view(request):
    app_settings = UserSettings.for_user(request.user)
    if request.method == 'POST':
        form = SettingsForm(request.POST, instance=app_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved.')
            return redirect('settings')
    else:
        form = SettingsForm(instance=app_settings)
    return render(request, 'expenses/settings.html', {'form': form})


@login_required
def group_detail(request, pk):
    group = _group_for_member(request, pk)
    expenses = group.expenses.select_related('paid_by').prefetch_related('splits__member')

    # Per-member owed totals across this group.
    owed = defaultdict(Decimal)
    for expense in expenses:
        for split in expense.splits.all():
            owed[split.member] += split.share
    balances = sorted(owed.items(), key=lambda kv: kv[0].name)

    memberships = group.memberships.select_related('user', 'member')
    local_members = group.local_members.all()
    is_admin = group.is_admin(request.user)

    return render(request, 'expenses/group_detail.html', {
        'group': group,
        'expenses': expenses,
        'balances': balances,
        'memberships': memberships,
        'local_members': local_members,
        'is_admin': is_admin,
        'invite': GroupInvite.for_group(group) if is_admin else None,
    })


@login_required
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if not group.is_admin(request.user):
        messages.error(request, 'Only the group admin can delete it.')
        return redirect('group_detail', pk=pk)
    if request.method == 'POST':
        name = group.name
        group.delete()
        messages.success(request, f'Group "{name}" deleted.')
        return redirect('group_list')
    return redirect('group_detail', pk=pk)


# ---------------------------------------------------------------------------
# Membership: invite, join, add local member, remove member
# ---------------------------------------------------------------------------

@login_required
def group_invite(request, pk):
    """Admin-only: add a member by username (shareable link is shown inline)."""
    group = get_object_or_404(Group, pk=pk)
    if not group.is_admin(request.user):
        messages.error(request, 'Only the group admin can invite members.')
        return redirect('group_detail', pk=pk)

    if request.method == 'POST':
        kind = request.POST.get('kind')
        if kind == 'username':
            username = (request.POST.get('username') or '').strip()
            user = User.objects.filter(username__iexact=username).first()
            if not user:
                messages.error(request, f'No user named "{username}".')
            elif group.is_member(user):
                messages.error(request, f'{username} is already in this group.')
            else:
                GroupMembership.add_user(group, user)
                messages.success(request, f'Added {user.username} to the group.')
        elif kind == 'local':
            name = (request.POST.get('name') or '').strip()
            if not name:
                messages.error(request, 'Enter a name.')
            else:
                member, _ = Member.objects.get_or_create(
                    owner=group.owner, name=name, defaults={'user': None})
                member.local_groups.add(group)
                messages.success(request, f'Added "{name}" as a splitter.')
    return redirect('group_detail', pk=pk)


@login_required
def group_join(request, code):
    """Open an invite link; join the group on confirmation."""
    invite = get_object_or_404(GroupInvite, code=code)
    group = invite.group
    already = group.is_member(request.user)
    if request.method == 'POST' and not already:
        GroupMembership.add_user(group, request.user)
        messages.success(request, f'You joined "{group.name}".')
        return redirect('group_detail', pk=group.pk)
    return render(request, 'expenses/join.html', {
        'group': group,
        'already': already,
        'member_count': group.memberships.count(),
    })


@login_required
def member_remove(request, pk, member_pk):
    """Admin-only: remove a member (real user membership or local member) from a
    group. Past expense splits are preserved."""
    group = get_object_or_404(Group, pk=pk)
    if not group.is_admin(request.user):
        messages.error(request, 'Only the group admin can manage members.')
        return redirect('group_detail', pk=pk)
    if request.method != 'POST':
        return redirect('group_detail', pk=pk)

    member = get_object_or_404(Member, pk=member_pk)
    membership = group.memberships.filter(member=member).first()
    if membership:
        if membership.role == GroupMembership.ADMIN:
            messages.error(request, 'The admin can’t be removed. Delete the group instead.')
            return redirect('group_detail', pk=pk)
        name = member.name
        membership.delete()
    else:
        name = member.name
        member.local_groups.remove(group)
    messages.success(request, f'Removed "{name}" from the group.')
    return redirect('group_detail', pk=pk)


@login_required
def expense_create(request, pk):
    group = _group_for_member(request, pk)
    participants = group.participants()

    # Default selected splitters = the group's remembered preference, else all.
    remembered = set(group.last_splitters.values_list('id', flat=True))
    default_ids = remembered or set(participants.values_list('id', flat=True))

    # Default payer = the current user's member in this group.
    my_member = group.member_for(request.user)

    custom_shares = {}

    if request.method == 'POST':
        form = ExpenseForm(request.POST, participants=participants)
        split_type = request.POST.get('split_type', Expense.EQUAL)
        selected_ids = request.POST.getlist('splitters')
        selected = list(participants.filter(id__in=selected_ids))

        if form.is_valid():
            error = None
            shares_by_member = {}
            if not selected:
                error = 'Pick at least one member to split with.'
            elif split_type == Expense.CUSTOM:
                total = Decimal('0.00')
                for member in selected:
                    raw = (request.POST.get(f'share_{member.id}') or '').strip()
                    custom_shares[str(member.id)] = raw
                    try:
                        share = Decimal(raw or '0').quantize(Decimal('0.01'))
                    except (InvalidOperation, ValueError):
                        error = f'Enter a valid amount for {member.name}.'
                        break
                    if share < 0:
                        error = f'{member.name}’s share can’t be negative.'
                        break
                    shares_by_member[member] = share
                    total += share
                if not error and total != form.cleaned_data['amount']:
                    error = (f'Custom shares add up to {total} but the total is '
                             f'{form.cleaned_data["amount"]}. They must match.')

            if error:
                messages.error(request, error)
            else:
                expense = form.save(commit=False)
                expense.group = group
                expense.split_type = split_type
                expense.save()
                if split_type == Expense.CUSTOM:
                    expense.split_custom(shares_by_member)
                else:
                    expense.split_equally(selected)
                group.last_splitters.set(selected)
                messages.success(request, f'Added "{expense.title}".')
                return redirect('group_detail', pk=group.pk)
        default_ids = set(int(i) for i in selected_ids)
    else:
        form = ExpenseForm(participants=participants, initial={
            'paid_by': my_member.pk if my_member else None,
        })
        split_type = Expense.EQUAL

    return render(request, 'expenses/expense_form.html', {
        'group': group,
        'form': form,
        'all_members': participants,
        'default_ids': default_ids,
        'split_type': split_type,
        'custom_shares': custom_shares,
    })


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    group = expense.group
    if not group.is_member(request.user):
        from django.http import Http404
        raise Http404()
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted.')
    return redirect('group_detail', pk=group.pk)


@login_required
def member_list(request):
    # Only the user's own name-only splitters (real-user members are managed
    # per-group via invites).
    members = Member.objects.filter(owner=request.user, user__isnull=True)
    if request.method == 'POST':
        form = MemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.owner = request.user
            if Member.objects.filter(owner=request.user, name__iexact=member.name).exists():
                messages.error(request, f'"{member.name}" already exists.')
            else:
                member.save()
                messages.success(request, f'Added member "{member.name}".')
            return redirect('member_list')
    else:
        form = MemberForm()
    return render(request, 'expenses/member_list.html', {
        'members': members,
        'form': form,
    })


@login_required
def member_delete(request, pk):
    member = get_object_or_404(Member, pk=pk, owner=request.user, user__isnull=True)
    if request.method == 'POST':
        name = member.name
        member.delete()
        messages.success(request, f'Removed "{name}".')
    return redirect('member_list')


# ---------------------------------------------------------------------------
# Milk tracker
# ---------------------------------------------------------------------------

@login_required
def milk_tracker(request):
    """Show vendors with their running tally, pending entries, and payment
    history. Also handles adding a new vendor."""
    vendors = MilkVendor.objects.filter(owner=request.user).prefetch_related(
        'entries', 'payments')

    if request.method == 'POST':
        form = MilkVendorForm(request.POST)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.owner = request.user
            vendor.save()
            messages.success(request, f'Added vendor "{vendor.name}".')
            return redirect('milk_vendor', pk=vendor.pk)
    else:
        form = MilkVendorForm()

    return render(request, 'expenses/milk_tracker.html', {
        'vendors': vendors,
        'form': form,
    })


@login_required
def milk_vendor(request, pk):
    """A single vendor: add an entry here, see the pending tally and history."""
    vendor = get_object_or_404(MilkVendor, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = MilkEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.vendor = vendor
            entry.save()
            messages.success(request, f'Added {entry.litres} L.')
            return redirect('milk_vendor', pk=vendor.pk)
    else:
        form = MilkEntryForm()

    pending = vendor.pending_entries.all()
    payments = vendor.payments.prefetch_related('entries')

    return render(request, 'expenses/milk_vendor.html', {
        'vendor': vendor,
        'form': form,
        'pending': pending,
        'payments': payments,
    })


@login_required
def milk_vendor_edit(request, pk):
    vendor = get_object_or_404(MilkVendor, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = MilkVendorForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vendor updated.')
            return redirect('milk_vendor', pk=vendor.pk)
    else:
        form = MilkVendorForm(instance=vendor)
    return render(request, 'expenses/milk_vendor_edit.html', {
        'vendor': vendor,
        'form': form,
    })


@login_required
def milk_entry_delete(request, pk):
    entry = get_object_or_404(MilkEntry, pk=pk, vendor__owner=request.user)
    vendor_pk = entry.vendor.pk
    if request.method == 'POST':
        if entry.payment_id is not None:
            messages.error(request, 'Can’t delete an entry that’s already been paid.')
        else:
            entry.delete()
            messages.success(request, 'Entry removed.')
    return redirect('milk_vendor', pk=vendor_pk)


@login_required
def milk_pay(request, pk):
    """Settle the current cycle: snapshot the pending litres+amount into a
    MilkPayment, stamp the pending entries, and reset the tally to zero."""
    vendor = get_object_or_404(MilkVendor, pk=pk, owner=request.user)
    if request.method == 'POST':
        pending = vendor.pending_entries
        litres = vendor.pending_litres
        if litres <= 0:
            messages.error(request, 'Nothing pending to pay.')
        else:
            payment = MilkPayment.objects.create(
                vendor=vendor,
                total_litres=litres,
                amount=vendor.pending_amount,
            )
            pending.update(payment=payment)
            messages.success(
                request,
                f'Paid for {litres} L. Tally reset to zero.',
            )
    return redirect('milk_vendor', pk=vendor.pk)


@login_required
def milk_vendor_delete(request, pk):
    vendor = get_object_or_404(MilkVendor, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = vendor.name
        vendor.delete()
        messages.success(request, f'Deleted vendor "{name}".')
        return redirect('milk_tracker')
    return redirect('milk_vendor', pk=pk)
