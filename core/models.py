from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)

# =========================
# CUSTOM USER MANAGER
# =========================
class UserManager(BaseUserManager):
    def create_user(self, email, name, phone, role, password=None):
        if not email:
            raise ValueError("User must have an email address")

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            name=name,
            phone=phone,
            role=role,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, phone, role="admin", password=None):
        user = self.create_user(email, name, phone, role, password)
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

# =========================
# CUSTOM USER MODEL
# =========================
class User(AbstractBaseUser, PermissionsMixin):
    # UPDATED: Matches the 'value' tags in your signup.html
    ROLE_CHOICES = [
        ('customer', 'Vehicle Owner'),
        ('provider', 'Mechanic / Technician'),
        ('admin', 'Garage Manager'),
    ]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    
    # Standard Django flags
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "phone", "role"] # Added role here

    def __str__(self):
        return self.email

    # Mandatory methods for Custom User models
    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return True