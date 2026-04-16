from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Expense, Friend, Group, SplitExpense


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['name', 'amount', 'date', 'is_long_term', 'end_date', 'interest_rate']


class FriendForm(forms.ModelForm):
    class Meta:
        model = Friend
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter friend name'})
        }


class GroupForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=Friend.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Group
        fields = ['name', 'members']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter group name'})
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['members'].queryset = Friend.objects.filter(user=user)


class SplitExpenseForm(forms.ModelForm):
    class Meta:
        model = SplitExpense
        fields = ['group', 'title', 'total_amount', 'paid_by']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Expense title'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'group': forms.Select(attrs={'class': 'form-control', 'id': 'group-select'}),
            'paid_by': forms.Select(attrs={'class': 'form-control', 'id': 'paid-by-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['paid_by'].queryset = Friend.objects.none()

        if user:
            self.fields['group'].queryset = Group.objects.filter(user=user)

        if 'group' in self.data:
            try:
                group_id = int(self.data.get('group'))
                self.fields['paid_by'].queryset = Friend.objects.filter(groupmember__group_id=group_id).distinct()
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['paid_by'].queryset = Friend.objects.filter(
                groupmember__group=self.instance.group
            ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        group = cleaned_data.get('group')
        paid_by = cleaned_data.get('paid_by')

        if group and paid_by:
            is_member = Friend.objects.filter(
                id=paid_by.id,
                groupmember__group=group
            ).exists()

            if not is_member:
                raise forms.ValidationError("Paid by must be a member of the selected group.")

        return cleaned_data