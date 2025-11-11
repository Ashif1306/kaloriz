from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import UserProfile
from catalog.models import Testimonial


class CustomUserRegistrationForm(UserCreationForm):
    """Custom registration form with additional fields"""

    # Basic fields
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Nama Lengkap',
        widget=forms.TextInput(attrs={
            'class': 'auth-input',
            'placeholder': 'Masukkan nama lengkap Anda'
        })
    )

    email = forms.EmailField(
        required=True,
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'class': 'auth-input',
            'placeholder': 'contoh@email.com'
        })
    )

    # Password fields (inherited from UserCreationForm but customized)
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'auth-input',
            'placeholder': 'Masukkan password'
        })
    )

    password2 = forms.CharField(
        label='Konfirmasi Password',
        widget=forms.PasswordInput(attrs={
            'class': 'auth-input',
            'placeholder': 'Masukkan ulang password'
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field requirement, we'll use email as username
        if 'username' in self.fields:
            self.fields.pop('username')

    def clean_email(self):
        """Validate that email is unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Email ini sudah terdaftar.')
        return email

    def save(self, commit=True):
        """Save user and create profile with additional fields"""
        # Create user with email as username
        email = self.cleaned_data['email']
        user = User(
            username=email,  # Use email as username
            email=email,
            first_name=self.cleaned_data['first_name']
        )
        user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()

            # Create user profile with additional fields
            UserProfile.objects.create(user=user)

        return user


class TestimonialForm(forms.ModelForm):
    """Form for customers to submit product testimonials."""

    class Meta:
        model = Testimonial
        fields = ['rating', 'review', 'photo']
        widgets = {
            'rating': forms.Select(
                attrs={
                    'class': 'custom-select custom-select-sm',
                    'required': True,
                }
            ),
            'review': forms.Textarea(
                attrs={
                    'class': 'form-control form-control-sm',
                    'rows': 3,
                    'placeholder': 'Ceritakan pengalaman Anda menggunakan produk ini',
                    'required': True,
                }
            ),
            'photo': forms.ClearableFileInput(
                attrs={
                    'class': 'form-control-file',
                    'accept': 'image/*',
                }
            ),
        }
        labels = {
            'rating': 'Rating',
            'review': 'Ulasan',
            'photo': 'Foto (Opsional)',
        }

