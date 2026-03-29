from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Organization, User

ORG_NONE = ''
ORG_NEW = '__new__'


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=User.Role.choices)
    organization_choice = forms.ChoiceField(
        required=False,
        label='Organization',
    )
    new_organization_name = forms.CharField(
        max_length=255,
        required=False,
        label='New organization name',
        help_text='Enter the exact name of your NGO or company.',
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (ORG_NONE, '— No organization —'),
            (ORG_NEW, '+ Create new organization'),
        ]
        for org in Organization.objects.order_by('name'):
            label = org.name
            if org.is_verified:
                label += ' (verified)'
            choices.append((str(org.pk), label))
        self.fields['organization_choice'].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        org_choice = cleaned_data.get('organization_choice', ORG_NONE)
        new_org_name = cleaned_data.get('new_organization_name', '').strip()

        if role == User.Role.COORDINATOR and org_choice == ORG_NEW:
            if not new_org_name:
                self.add_error('new_organization_name', 'Please enter an organization name.')
            elif Organization.objects.filter(name__iexact=new_org_name).exists():
                self.add_error(
                    'new_organization_name',
                    'An organization with this name already exists. Please select it from the list.',
                )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        # Volunteers are auto-verified; coordinators wait for admin/org verification
        if user.role == User.Role.VOLUNTEER:
            user.is_verified = True
        else:
            user.is_verified = False
        if commit:
            user.save()
        return user
