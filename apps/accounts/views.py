from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
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
        messages.info(request, "This page is only available for coordinators of verified organizations.")
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
        messages.success(request, "Your account has been permanently deleted.")
        return redirect('accounts:login')
    return render(request, 'accounts/delete_account.html')


@login_required
def coordinator_profile(request):
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')

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
        messages.error(request, "You are already in an organisation. Leave it first.")
        return redirect('accounts:coordinator_profile')

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, "Organisation name cannot be empty.")
        return redirect('accounts:coordinator_profile')
    if Organization.objects.filter(name__iexact=name).exists():
        messages.error(request, "An organisation with that name already exists.")
        return redirect('accounts:coordinator_profile')

    org = Organization.objects.create(name=name, created_by=user)
    user.organization = org
    user.save(update_fields=['organization'])
    messages.success(request, f"Organisation '{org.name}' created. It will appear as verified once an admin approves it.")
    return redirect('accounts:coordinator_profile')


@login_required
@require_POST
def coordinator_org_join(request):
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')
    if user.organization:
        messages.error(request, "You are already in an organisation. Leave it first.")
        return redirect('accounts:coordinator_profile')

    org_id = request.POST.get('org_id', '').strip()
    try:
        org = Organization.objects.get(pk=int(org_id))
    except (Organization.DoesNotExist, ValueError):
        messages.error(request, "Organisation not found.")
        return redirect('accounts:coordinator_profile')

    user.organization = org
    user.is_verified = False
    user.save(update_fields=['organization', 'is_verified'])
    messages.success(request, f"You have joined '{org.name}' and are pending verification by an existing member.")
    return redirect('accounts:pending_verification')


@login_required
@require_POST
def coordinator_org_leave(request):
    user = request.user
    if not user.is_coordinator():
        return redirect('tasks:task_list')
    if not user.organization:
        messages.error(request, "You are not in any organisation.")
        return redirect('accounts:coordinator_profile')

    org_name = user.organization.name
    user.organization = None
    user.is_verified = False
    user.save(update_fields=['organization', 'is_verified'])
    messages.success(request, f"You have left '{org_name}'. Your account will need re-verification.")
    return redirect('accounts:coordinator_profile')


@login_required
@require_POST
def verify_coordinator(request, pk):
    """POST action: verify a specific coordinator within the same org."""
    user = request.user
    if not user.is_coordinator() or not user.is_verified:
        messages.error(request, "You do not have permission to verify coordinators.")
        return redirect('tasks:task_list')

    org = user.organization
    if org is None or not org.is_verified:
        messages.error(request, "Only coordinators of verified organizations can verify members.")
        return redirect('tasks:task_list')

    target = get_object_or_404(
        User, pk=pk, organization=org, role=User.Role.COORDINATOR, is_verified=False
    )
    target.is_verified = True
    target.save(update_fields=['is_verified'])
    messages.success(request, f"{target.username} has been verified and can now use the platform.")
    return redirect('accounts:verify_coordinators')


@login_required
@require_POST
def decline_coordinator(request, pk):
    """POST action: decline a pending coordinator — removes them from the org."""
    user = request.user
    if not user.is_coordinator() or not user.is_verified:
        messages.error(request, "You do not have permission to decline coordinators.")
        return redirect('tasks:task_list')

    org = user.organization
    if org is None or not org.is_verified:
        messages.error(request, "Only coordinators of verified organizations can manage members.")
        return redirect('tasks:task_list')

    target = get_object_or_404(
        User, pk=pk, organization=org, role=User.Role.COORDINATOR, is_verified=False
    )
    target.organization = None
    target.save(update_fields=['organization'])
    messages.warning(request, f"{target.username}'s request has been declined and they have been removed from the organisation.")
    return redirect('accounts:verify_coordinators')
