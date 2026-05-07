from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from apps.tasks.models import Task
from .forms import ORG_NEW, RegistrationForm
from .models import Organization, User


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('tasks:task_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('tasks:task_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save(commit=False)
        org_choice = form.cleaned_data.get('organization_choice', '')
        new_org_name = form.cleaned_data.get('new_organization_name', '').strip()

        if user.role == User.Role.COORDINATOR:
            if org_choice == ORG_NEW and new_org_name:
                org = Organization.objects.create(name=new_org_name)
                user.organization = org
            elif org_choice and org_choice != ORG_NEW:
                try:
                    user.organization = Organization.objects.get(pk=int(org_choice))
                except (Organization.DoesNotExist, ValueError):
                    pass

        user.save()

        # Set created_by after user has a PK
        if user.role == User.Role.COORDINATOR and org_choice == ORG_NEW and new_org_name:
            user.organization.created_by = user
            user.organization.save(update_fields=['created_by'])

        login(self.request, user)

        if user.is_coordinator() and not user.is_verified:
            return redirect('accounts:pending_verification')
        return redirect(self.success_url)


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('tasks:task_list')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return reverse_lazy('accounts:admin_dashboard')
        if user.is_coordinator() and not user.is_verified:
            return reverse_lazy('accounts:pending_verification')
        return super().get_success_url()


@login_required
def pending_verification(request):
    """Shown to coordinators who are not yet verified."""
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')
    if user.is_verified:
        return redirect('tasks:task_list')

    org = user.organization
    org_has_verifiers = (
        org is not None
        and org.is_verified
        and org.members.filter(role=User.Role.COORDINATOR, is_verified=True).exclude(pk=user.pk).exists()
    )
    return render(request, 'accounts/pending_verification.html', {
        'org': org,
        'org_has_verifiers': org_has_verifiers,
    })


@login_required
def verify_coordinators(request):
    """
    Verified coordinators of a verified organization can verify
    other pending coordinators in their org.
    """
    user = request.user
    if not user.is_coordinator() or not user.is_verified:
        return redirect('tasks:task_list')

    org = user.organization
    if org is None or not org.is_verified:
        messages.info(request, "Ця сторінка доступна лише координаторам верифікованих організацій.")
        return redirect('tasks:task_list')

    pending = (
        User.objects
        .filter(organization=org, role=User.Role.COORDINATOR, is_verified=False)
        .exclude(pk=user.pk)
    )
    return render(request, 'accounts/verify_coordinators.html', {
        'org': org,
        'pending': pending,
    })


@login_required
def delete_account(request):
    """
    GET: show confirmation page.
    POST: soft-delete the account (is_active=False + deleted_at timestamp).
    All task history is preserved in the database.
    """
    if request.method == 'POST':
        user = request.user
        user.is_active = False
        user.deleted_at = timezone.now()
        user.save(update_fields=['is_active', 'deleted_at'])
        logout(request)
        messages.success(request, "Ваш акаунт було назавжди видалено.")
        return redirect('accounts:login')
    return render(request, 'accounts/delete_account.html')


@login_required
def coordinator_profile(request):
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')

    if request.method == 'POST' and 'update_name' in request.POST:
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.save(update_fields=['first_name', 'last_name'])
        messages.success(request, "Ім'я оновлено.")
        return redirect('accounts:coordinator_profile')

    user_tasks = Task.objects.filter(created_by=user)
    personal_stats = {
        'total':       user_tasks.count(),
        'open':        user_tasks.filter(status=Task.Status.OPEN, is_archived=False).count(),
        'in_progress': user_tasks.filter(status=Task.Status.IN_PROGRESS, is_archived=False).count(),
        'completed':   user_tasks.filter(status=Task.Status.COMPLETED).count(),
        'archived':    user_tasks.filter(is_archived=True).count(),
    }

    org_stats = None
    if user.organization:
        org_tasks = Task.objects.filter(created_by__organization=user.organization)
        org_stats = {
            'total':       org_tasks.count(),
            'open':        org_tasks.filter(status=Task.Status.OPEN, is_archived=False).count(),
            'in_progress': org_tasks.filter(status=Task.Status.IN_PROGRESS, is_archived=False).count(),
            'completed':   org_tasks.filter(status=Task.Status.COMPLETED).count(),
            'archived':    org_tasks.filter(is_archived=True).count(),
        }

    other_orgs = Organization.objects.exclude(pk=user.organization_id) if user.organization else Organization.objects.all()

    return render(request, 'accounts/coordinator_profile.html', {
        'personal_stats': personal_stats,
        'org_stats':      org_stats,
        'other_orgs':     other_orgs,
    })


@login_required
@require_POST
def coordinator_org_create(request):
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')
    if user.organization:
        messages.error(request, "Ви вже є членом організації. Спочатку покиньте її.")
        return redirect('accounts:coordinator_profile')

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, "Назва організації не може бути порожньою.")
        return redirect('accounts:coordinator_profile')
    if Organization.objects.filter(name__iexact=name).exists():
        messages.error(request, "Організація з такою назвою вже існує.")
        return redirect('accounts:coordinator_profile')

    org = Organization.objects.create(name=name, created_by=user)
    user.organization = org
    user.save(update_fields=['organization'])
    messages.success(request, f"Організацію '{org.name}' створено. Вона стане верифікованою після схвалення адміністратором.")
    return redirect('accounts:coordinator_profile')


@login_required
@require_POST
def coordinator_org_join(request):
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')
    if user.organization:
        messages.error(request, "Ви вже є членом організації. Спочатку покиньте її.")
        return redirect('accounts:coordinator_profile')

    org_id = request.POST.get('org_id', '').strip()
    try:
        org = Organization.objects.get(pk=int(org_id))
    except (Organization.DoesNotExist, ValueError):
        messages.error(request, "Організацію не знайдено.")
        return redirect('accounts:coordinator_profile')

    user.organization = org
    user.is_verified = False
    user.save(update_fields=['organization', 'is_verified'])
    messages.success(request, f"Ви приєдналися до '{org.name}' та очікуєте верифікації від існуючого учасника.")
    return redirect('accounts:pending_verification')


@login_required
@require_POST
def coordinator_org_leave(request):
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')
    if not user.organization:
        messages.error(request, "Ви не є членом жодної організації.")
        return redirect('accounts:coordinator_profile')

    org_name = user.organization.name
    user.organization = None
    user.is_verified = False
    user.save(update_fields=['organization', 'is_verified'])
    messages.success(request, f"Ви покинули '{org_name}'. Ваш акаунт потребуватиме повторної верифікації.")
    return redirect('accounts:coordinator_profile')


@login_required
@require_POST
def verify_coordinator(request, pk):
    """POST action: verify a specific coordinator within the same org."""
    user = request.user
    if not user.is_coordinator() or not user.is_verified:
        messages.error(request, "У вас немає дозволу верифікувати координаторів.")
        return redirect('tasks:task_list')

    org = user.organization
    if org is None or not org.is_verified:
        messages.error(request, "Лише координатори верифікованих організацій можуть верифікувати учасників.")
        return redirect('tasks:task_list')

    target = get_object_or_404(
        User, pk=pk, organization=org, role=User.Role.COORDINATOR, is_verified=False
    )
    target.is_verified = True
    target.save(update_fields=['is_verified'])
    messages.success(request, f"{target.username} верифіковано та може користуватися платформою.")
    return redirect('accounts:verify_coordinators')


@login_required
@require_POST
def decline_coordinator(request, pk):
    """POST action: decline a pending coordinator — removes them from the org."""
    user = request.user
    if not user.is_coordinator() or not user.is_verified:
        messages.error(request, "У вас немає дозволу відхиляти координаторів.")
        return redirect('tasks:task_list')

    org = user.organization
    if org is None or not org.is_verified:
        messages.error(request, "Лише координатори верифікованих організацій можуть керувати учасниками.")
        return redirect('tasks:task_list')

    target = get_object_or_404(
        User, pk=pk, organization=org, role=User.Role.COORDINATOR, is_verified=False
    )
    target.organization = None
    target.save(update_fields=['organization'])
    messages.warning(request, f"Запит {target.username} відхилено, їх видалено з організації.")
    return redirect('accounts:verify_coordinators')


# ---------------------------------------------------------------------------
# Admin panel views (superuser only)
# ---------------------------------------------------------------------------

def _require_superuser(request):
    """Return a redirect response if the user is not a superuser, else None."""
    if not request.user.is_superuser:
        return redirect('tasks:task_list')
    return None


@login_required
def admin_dashboard(request):
    guard = _require_superuser(request)
    if guard:
        return guard

    stats = {
        'total_users':           User.objects.filter(is_active=True, is_superuser=False).count(),
        'volunteers':            User.objects.filter(role=User.Role.VOLUNTEER, is_active=True).count(),
        'coordinators':          User.objects.filter(role=User.Role.COORDINATOR, is_active=True).count(),
        'pending_coordinators':  User.objects.filter(role=User.Role.COORDINATOR, is_verified=False, is_active=True).count(),
        'total_orgs':            Organization.objects.count(),
        'pending_orgs':          Organization.objects.filter(is_verified=False).count(),
        'total_tasks':           Task.objects.filter(is_archived=False).count(),
        'open_tasks':            Task.objects.filter(status=Task.Status.OPEN, is_archived=False).count(),
    }
    return render(request, 'admin_panel/dashboard.html', {'stats': stats})


@login_required
def admin_users(request):
    guard = _require_superuser(request)
    if guard:
        return guard

    role_filter = request.GET.get('role', '')
    verified_filter = request.GET.get('verified', '')

    users = (
        User.objects
        .filter(is_active=True, is_superuser=False)
        .select_related('organization')
        .order_by('role', 'username')
    )
    if role_filter:
        users = users.filter(role=role_filter)
    if verified_filter == 'pending':
        users = users.filter(role=User.Role.COORDINATOR, is_verified=False)
    elif verified_filter == 'verified':
        users = users.filter(is_verified=True)

    return render(request, 'admin_panel/users.html', {
        'users': users,
        'role_filter': role_filter,
        'verified_filter': verified_filter,
    })


@login_required
def admin_organizations(request):
    guard = _require_superuser(request)
    if guard:
        return guard

    orgs = (
        Organization.objects
        .annotate(member_count=Count('members'))
        .select_related('created_by')
        .order_by('is_verified', 'name')
    )
    return render(request, 'admin_panel/organizations.html', {'orgs': orgs})


@login_required
@require_POST
def admin_verify_organization(request, pk):
    guard = _require_superuser(request)
    if guard:
        return guard

    org = get_object_or_404(Organization, pk=pk)
    org.is_verified = True
    org.save(update_fields=['is_verified'])
    messages.success(request, f"Організацію '{org.name}' верифіковано.")
    return redirect('accounts:admin_organizations')


@login_required
@require_POST
def admin_verify_coordinator(request, pk):
    guard = _require_superuser(request)
    if guard:
        return guard

    target = get_object_or_404(User, pk=pk, role=User.Role.COORDINATOR)
    target.is_verified = True
    target.save(update_fields=['is_verified'])
    messages.success(request, f"{target.username} верифіковано.")
    return redirect('accounts:admin_users')


@login_required
@require_POST
def admin_delete_user(request, pk):
    guard = _require_superuser(request)
    if guard:
        return guard

    target = get_object_or_404(User, pk=pk, is_superuser=False)
    target.is_active = False
    target.deleted_at = timezone.now()
    target.save(update_fields=['is_active', 'deleted_at'])
    messages.success(request, f"Користувача '{target.username}' видалено.")
    return redirect('accounts:admin_users')


@login_required
@require_POST
def admin_delete_organization(request, pk):
    guard = _require_superuser(request)
    if guard:
        return guard

    org = get_object_or_404(Organization, pk=pk)
    org_name = org.name
    # Unverify coordinators who belonged to this org before SET_NULL fires
    User.objects.filter(organization=org, role=User.Role.COORDINATOR).update(is_verified=False)
    org.delete()
    messages.success(request, f"Організацію '{org_name}' видалено.")
    return redirect('accounts:admin_organizations')
