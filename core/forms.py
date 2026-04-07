"""
core/forms.py
─────────────
All Django forms for eGarage.
"""

from django import forms
from django.contrib.auth.password_validation import validate_password
from .models import User, Vehicle, Booking


class UserSignupForm(forms.Form):
    name     = forms.CharField(max_length=120)
    email    = forms.EmailField()
    phone    = forms.CharField(max_length=15, required=False)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    confirm  = forms.CharField(widget=forms.PasswordInput)
    role     = forms.ChoiceField(choices=[
        ('owner',    'Vehicle Owner'),
        ('mechanic', 'Mechanic'),
        ('manager',  'Garage Manager'),
    ])
    city = forms.CharField(max_length=60, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class LoginForm(forms.Form):
    email    = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model  = User
        fields = ['name', 'phone', 'city', 'profile_photo',
                  'date_of_birth', 'gender', 'address', 'whatsapp', 'emergency_contact']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password     = forms.CharField(min_length=8, widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password') != cleaned.get('confirm_password'):
            raise forms.ValidationError('New passwords do not match.')
        return cleaned


class VehicleForm(forms.ModelForm):
    class Meta:
        model  = Vehicle
        fields = ['type', 'brand', 'model_name', 'variant', 'registration_number',
                  'year', 'fuel_type', 'colour', 'odometer', 'insurance_expiry', 'is_primary']
        widgets = {
            'insurance_expiry': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['variant', 'registration_number', 'year',
                  'colour', 'odometer', 'insurance_expiry']:
            self.fields[f].required = False


class ReviewForm(forms.Form):
    rating = forms.IntegerField(min_value=1, max_value=5)
    text   = forms.CharField(required=False, widget=forms.Textarea)
    # aspect checkboxes
    aspect_quality   = forms.BooleanField(required=False)
    aspect_time      = forms.BooleanField(required=False)
    aspect_clean     = forms.BooleanField(required=False)
    aspect_polite    = forms.BooleanField(required=False)
    aspect_price     = forms.BooleanField(required=False)
    aspect_recommend = forms.BooleanField(required=False)