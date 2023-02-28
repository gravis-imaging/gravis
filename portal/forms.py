from django import forms
from django.contrib.auth.models import User

from . models import UserProfile


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('__all__')


class ProfileUpdateForm(forms.Form):
    privacy_mode = forms.BooleanField(required=False)
