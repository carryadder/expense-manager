from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Expense, Group, Member, UserSettings


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. FLAT, TRIP, OFFICE'}),
            'icon': forms.HiddenInput(),
        }


class SettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ['display_name', 'currency', 'date_format']
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Your name'}),
            'currency': forms.Select(),
            'date_format': forms.Select(),
        }


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Member name'}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'amount', 'note', 'paid_by']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'What was it for?'}),
            'amount': forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'note': forms.Textarea(attrs={'placeholder': 'Optional note…', 'rows': 2}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields['paid_by'].queryset = Member.objects.filter(owner=owner)
        self.fields['paid_by'].required = False
        self.fields['paid_by'].empty_label = '— nobody / shared —'
