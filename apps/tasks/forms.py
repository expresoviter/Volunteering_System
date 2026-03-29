from django import forms
from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'description', 'address', 'priority', 'volunteers_needed')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'volunteers_needed': forms.NumberInput(attrs={'min': 1, 'max': 100}),
        }
