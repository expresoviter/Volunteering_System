from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Organization, User

ORG_NONE = ''
ORG_NEW = '__new__'


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Електронна пошта")
    role = forms.ChoiceField(choices=User.Role.choices, label="Роль")
    organization_choice = forms.ChoiceField(
        required=False,
        label='Організація',
    )
    new_organization_name = forms.CharField(
        max_length=255,
        required=False,
        label='Назва нової організації',
        help_text='Введіть точну назву вашої НГО або компанії.',
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Ім'я користувача"
        self.fields['password1'].label = "Пароль"
        self.fields['password2'].label = "Підтвердження паролю"
        choices = [
            (ORG_NONE, '— Без організації —'),
            (ORG_NEW, '+ Створити нову організацію'),
        ]
        for org in Organization.objects.order_by('name'):
            label = org.name
            if org.is_verified:
                label += ' (верифікована)'
            choices.append((str(org.pk), label))
        self.fields['organization_choice'].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            self.add_error('email', 'Користувач з такою електронною адресою вже існує.')

        role = cleaned_data.get('role')
        org_choice = cleaned_data.get('organization_choice', ORG_NONE)
        new_org_name = cleaned_data.get('new_organization_name', '').strip()

        if role == User.Role.COORDINATOR and org_choice == ORG_NEW:
            if not new_org_name:
                self.add_error('new_organization_name', 'Будь ласка, введіть назву організації.')
            elif Organization.objects.filter(name__iexact=new_org_name).exists():
                self.add_error(
                    'new_organization_name',
                    'Організація з такою назвою вже існує. Будь ласка, оберіть її зі списку.',
                )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        user.is_verified = user.role == User.Role.VOLUNTEER
        if commit:
            user.save()
        return user
