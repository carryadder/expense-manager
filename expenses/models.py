import secrets
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models

INVITE_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'


def generate_invite_code():
    return ''.join(secrets.choice(INVITE_ALPHABET) for _ in range(8))

# (code, symbol, label) — the currencies offered on the settings page.
CURRENCIES = [
    ('USD', '$', 'US Dollar'),
    ('INR', '₹', 'Indian Rupee'),
    ('EUR', '€', 'Euro'),
    ('GBP', '£', 'British Pound'),
    ('JPY', '¥', 'Japanese Yen'),
    ('AUD', 'A$', 'Australian Dollar'),
    ('CAD', 'C$', 'Canadian Dollar'),
    ('AED', 'د.إ', 'UAE Dirham'),
]
CURRENCY_SYMBOLS = {code: symbol for code, symbol, _ in CURRENCIES}


class UserSettings(models.Model):
    """Per-user preferences applied across the app."""
    DATE_RELATIVE = 'relative'
    DATE_DMY = 'dmy'
    DATE_MDY = 'mdy'
    DATE_ISO = 'iso'
    DATE_CHOICES = [
        (DATE_RELATIVE, 'Relative (e.g. 2 days ago)'),
        (DATE_DMY, 'DD/MM/YYYY'),
        (DATE_MDY, 'MM/DD/YYYY'),
        (DATE_ISO, 'YYYY-MM-DD'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='settings',
    )
    display_name = models.CharField(max_length=80, blank=True)
    currency = models.CharField(
        max_length=3,
        choices=[(c, f'{c} ({s})') for c, s, _ in CURRENCIES],
        default='USD',
    )
    date_format = models.CharField(max_length=10, choices=DATE_CHOICES, default=DATE_RELATIVE)

    def __str__(self):
        return f'Settings for {self.user}'

    @property
    def currency_symbol(self):
        return CURRENCY_SYMBOLS.get(self.currency, '$')

    @property
    def name(self):
        return self.display_name or self.user.username

    @classmethod
    def for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj


class Member(models.Model):
    """A person who can participate in expense splits.

    A member is either a plain name-label (``user`` is null, created by
    ``owner``) or is backed by a real invited user (``user`` set). Splits always
    target a Member, so the same splitting logic serves both kinds.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='members',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='member_identities',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=80)
    # Groups this name-only member has been added to by an admin. Real-user
    # members participate via GroupMembership instead and leave this empty.
    local_groups = models.ManyToManyField(
        'Group', related_name='local_members', blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [('owner', 'name')]

    def __str__(self):
        return self.name

    @property
    def is_user(self):
        return self.user_id is not None

    @property
    def initials(self):
        parts = self.name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return self.name[:2].upper()


class Group(models.Model):
    """A context for expenses, e.g. 'FLAT'. Remembers the last splitter set."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='expense_groups',
    )
    name = models.CharField(max_length=80)
    # Key into the SVG icon set (see expenses/icons.py).
    icon = models.CharField(max_length=24, default='wallet')
    # Remembered splitter preference: used as the default the next time an
    # expense is added in this group.
    last_splitters = models.ManyToManyField(
        Member,
        related_name='default_in_groups',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('owner', 'name')]

    def __str__(self):
        return self.name

    @property
    def total(self):
        agg = self.expenses.aggregate(s=models.Sum('amount'))
        return agg['s'] or Decimal('0.00')

    @property
    def expense_count(self):
        return self.expenses.count()

    def is_admin(self, user):
        return self.memberships.filter(user=user, role=GroupMembership.ADMIN).exists()

    def is_member(self, user):
        return self.memberships.filter(user=user).exists()

    def member_for(self, user):
        """The Member row this user splits as, in this group (or None)."""
        ms = self.memberships.filter(user=user).select_related('member').first()
        return ms.member if ms else None

    def participants(self):
        """All Member rows splittable in this group: every membership's member
        plus any name-only local members the admin added to the group."""
        ids = set(self.memberships.values_list('member_id', flat=True))
        ids.update(self.local_members.values_list('id', flat=True))
        return Member.objects.filter(id__in=ids)


class GroupMembership(models.Model):
    """Links a real user to a shared group, with a role and the Member row the
    user splits as within that group."""
    ADMIN = 'admin'
    MEMBER = 'member'
    ROLE_CHOICES = [(ADMIN, 'Admin'), (MEMBER, 'Member')]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_memberships',
    )
    member = models.ForeignKey(
        'Member', on_delete=models.CASCADE, related_name='memberships',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['joined_at']
        unique_together = [('group', 'user')]

    def __str__(self):
        return f'{self.user} in {self.group} ({self.role})'

    @classmethod
    def add_user(cls, group, user, role=None):
        """Add a user to a group as a real-user member. Idempotent — returns the
        existing membership if the user is already in the group."""
        existing = cls.objects.filter(group=group, user=user).first()
        if existing:
            return existing
        role = role or cls.MEMBER
        # Reuse this user's self-member if present, else create one.
        display = (getattr(user, 'settings', None) and user.settings.name) or user.username
        member = Member.objects.filter(owner=group.owner, user=user).first()
        if member is None:
            name = display
            # Avoid colliding with an existing name-label for this owner.
            if Member.objects.filter(owner=group.owner, name=name).exists():
                name = f'{display} (@{user.username})'
            member = Member.objects.create(owner=group.owner, user=user, name=name)
        return cls.objects.create(group=group, user=user, member=member, role=role)


class GroupInvite(models.Model):
    """A shareable join code for a group."""
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='invite')
    code = models.CharField(max_length=20, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'invite:{self.code}'

    @classmethod
    def for_group(cls, group):
        """Get the group's invite, creating one with a unique code if absent."""
        invite = cls.objects.filter(group=group).first()
        if invite:
            return invite
        while True:
            code = generate_invite_code()
            if not cls.objects.filter(code=code).exists():
                return cls.objects.create(group=group, code=code)


class Expense(models.Model):
    EQUAL = 'equal'
    CUSTOM = 'custom'
    SPLIT_CHOICES = [(EQUAL, 'Equal'), (CUSTOM, 'Custom')]

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='expenses',
    )
    title = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    split_type = models.CharField(max_length=10, choices=SPLIT_CHOICES, default=EQUAL)
    note = models.TextField(blank=True)
    paid_by = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paid_expenses',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.amount})'

    def split_equally(self, members):
        """Create ExpenseSplit rows dividing the amount evenly, with any
        rounding remainder absorbed by the first member so shares sum exactly."""
        members = list(members)
        self.splits.all().delete()
        if not members:
            return
        n = len(members)
        base = (self.amount / n).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        shares = [base] * n
        remainder = self.amount - base * n
        shares[0] = (shares[0] + remainder).quantize(Decimal('0.01'))
        for member, share in zip(members, shares):
            ExpenseSplit.objects.create(
                expense=self, member=member, share=share,
            )

    def split_custom(self, shares_by_member):
        """Create ExpenseSplit rows from an explicit {member: Decimal} map.
        The caller is responsible for validating the shares sum to the amount."""
        self.splits.all().delete()
        for member, share in shares_by_member.items():
            ExpenseSplit.objects.create(
                expense=self, member=member,
                share=Decimal(share).quantize(Decimal('0.01')),
            )


class ExpenseSplit(models.Model):
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='splits',
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='splits',
    )
    share = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [('expense', 'member')]

    def __str__(self):
        return f'{self.member.name}: {self.share}'


# ---------------------------------------------------------------------------
# Milk tracker: a running tally of litres taken from a vendor, reset on payment.
# ---------------------------------------------------------------------------

class MilkVendor(models.Model):
    """The milk supplier for a user, with a price per litre."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='milk_vendors',
    )
    name = models.CharField(max_length=80)
    price_per_litre = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def pending_entries(self):
        return self.entries.filter(payment__isnull=True)

    @property
    def pending_litres(self):
        agg = self.pending_entries.aggregate(s=models.Sum('litres'))
        return agg['s'] or Decimal('0.000')

    @property
    def pending_amount(self):
        return (self.pending_litres * self.price_per_litre).quantize(Decimal('0.01'))


class MilkPayment(models.Model):
    """A settled milk cycle — closes out the entries pending at payment time."""
    vendor = models.ForeignKey(
        MilkVendor,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    total_litres = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f'{self.vendor.name} paid {self.amount} for {self.total_litres} L'


class MilkEntry(models.Model):
    """One milk pickup: how many litres on a given day. Pending until its
    vendor is paid, at which point it's stamped with the MilkPayment."""
    vendor = models.ForeignKey(
        MilkVendor,
        on_delete=models.CASCADE,
        related_name='entries',
    )
    litres = models.DecimalField(max_digits=6, decimal_places=3)
    note = models.CharField(max_length=120, blank=True)
    payment = models.ForeignKey(
        MilkPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entries',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'milk entries'

    def __str__(self):
        return f'{self.litres} L from {self.vendor.name}'

    @property
    def amount(self):
        return (self.litres * self.vendor.price_per_litre).quantize(Decimal('0.01'))
