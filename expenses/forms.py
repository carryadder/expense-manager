from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Expense, Group, Member, MilkEntry, MilkVendor, UserSettings


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

    def __init__(self, *args, participants=None, **kwargs):
        super().__init__(*args, **kwargs)
        if participants is not None:
            self.fields['paid_by'].queryset = participants
        self.fields['paid_by'].required = False
        self.fields['paid_by'].empty_label = '— nobody / shared —'


class InviteUserForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Friend’s username'}),
    )


class MilkVendorForm(forms.ModelForm):
    class Meta:
        model = MilkVendor
        fields = ['name', 'price_per_litre']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Ramu the milkman'}),
            'price_per_litre': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }


class MilkEntryForm(forms.ModelForm):
    class Meta:
        model = MilkEntry
        fields = ['litres', 'note']
        widgets = {
            'litres': forms.NumberInput(attrs={'step': '0.25', 'min': '0', 'placeholder': 'e.g. 1 or 2'}),
            'note': forms.TextInput(attrs={'placeholder': 'Optional note'}),
        }

    def clean_litres(self):
        litres = self.cleaned_data['litres']
        if litres is None or litres <= 0:
            raise forms.ValidationError('Enter a litre amount greater than 0.')
        return litres
