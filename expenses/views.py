from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ExpenseForm, GroupForm, MemberForm, SettingsForm, SignUpForm
from .icons import GROUP_ICON_CHOICES
from .models import Expense, Group, Member, UserSettings


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
    groups = Group.objects.filter(owner=request.user)
    grand_total = groups.aggregate(s=Sum('expenses__amount'))['s'] or Decimal('0.00')
    return render(request, 'expenses/group_list.html', {
        'groups': groups,
        'grand_total': grand_total,
        'member_count': Member.objects.filter(owner=request.user).count(),
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
    group = get_object_or_404(Group, pk=pk, owner=request.user)
    expenses = group.expenses.select_related('paid_by').prefetch_related('splits__member')

    # Per-member owed totals across this group.
    owed = defaultdict(Decimal)
    for expense in expenses:
        for split in expense.splits.all():
            owed[split.member] += split.share
    balances = sorted(owed.items(), key=lambda kv: kv[0].name)

    return render(request, 'expenses/group_detail.html', {
        'group': group,
        'expenses': expenses,
        'balances': balances,
    })


@login_required
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = group.name
        group.delete()
        messages.success(request, f'Group "{name}" deleted.')
        return redirect('group_list')
    return redirect('group_detail', pk=pk)


@login_required
def expense_create(request, pk):
    group = get_object_or_404(Group, pk=pk, owner=request.user)
    all_members = Member.objects.filter(owner=request.user)

    # Default selected splitters = the group's remembered preference.
    default_ids = set(group.last_splitters.values_list('id', flat=True))

    # custom_shares maps member id (str) -> raw share string, to repopulate the
    # form after a validation error.
    custom_shares = {}

    if request.method == 'POST':
        form = ExpenseForm(request.POST, owner=request.user)
        split_type = request.POST.get('split_type', Expense.EQUAL)
        selected_ids = request.POST.getlist('splitters')
        selected = list(all_members.filter(id__in=selected_ids))

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
                    error = (f'Custom shares add up to ${total} but the total is '
                             f'${form.cleaned_data["amount"]}. They must match.')

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
                # Remember this splitter set as the group's new default.
                group.last_splitters.set(selected)
                messages.success(request, f'Added "{expense.title}".')
                return redirect('group_detail', pk=group.pk)
        default_ids = set(int(i) for i in selected_ids)
    else:
        form = ExpenseForm(owner=request.user)
        split_type = Expense.EQUAL

    return render(request, 'expenses/expense_form.html', {
        'group': group,
        'form': form,
        'all_members': all_members,
        'default_ids': default_ids,
        'split_type': split_type,
        'custom_shares': custom_shares,
    })


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, group__owner=request.user)
    group_pk = expense.group.pk
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted.')
    return redirect('group_detail', pk=group_pk)


@login_required
def member_list(request):
    members = Member.objects.filter(owner=request.user)
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
    member = get_object_or_404(Member, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = member.name
        member.delete()
        messages.success(request, f'Removed "{name}".')
    return redirect('member_list')
