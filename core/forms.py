from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class UserSignupForm(UserCreationForm):

    class Meta:
        model = User
        fields = ['email', 'name', 'phone', 'role']


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email")