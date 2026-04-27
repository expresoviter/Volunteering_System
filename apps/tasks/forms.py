from django import forms
from django.utils import timezone
from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'description', 'address', 'priority', 'volunteers_needed', 'start_date', 'end_date')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'volunteers_needed': forms.NumberInput(attrs={'min': 1, 'max': 100}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            today = timezone.localdate()
            self.fields['start_date'].initial = today
            self.fields['end_date'].initial = today
