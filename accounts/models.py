from django.conf import settings
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    MENTOR = "MENTOR", "Mentor"
    MANAGER = "MANAGER", "Manager"
    HR = "HR", "HR"
    INTERN = "INTERN", "Intern"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.INTERN)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"
