from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models

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
    """A person who can participate in expense splits, owned by a user."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='members',
    )
    name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [('owner', 'name')]

    def __str__(self):
        return self.name

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
