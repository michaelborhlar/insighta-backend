import uuid
from django.db import models


def generate_uuid7():
    # uuid7-like: time-ordered UUID using uuid1 bits rearranged
    # Using uuid4 as fallback since uuid7 library may not be available
    try:
        import uuid7 as _uuid7
        return str(_uuid7.uuid7())
    except ImportError:
        return str(uuid.uuid4())


class User(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_ANALYST = "analyst"
    ROLE_CHOICES = [(ROLE_ADMIN, "Admin"), (ROLE_ANALYST, "Analyst")]

    id = models.CharField(primary_key=True, max_length=36, default=generate_uuid7)
    github_id = models.CharField(max_length=64, unique=True)
    username = models.CharField(max_length=255)
    email = models.CharField(max_length=255, blank=True, default="")
    avatar_url = models.CharField(max_length=500, blank=True, default="")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_ANALYST)
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"@{self.username} ({self.role})"

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


class RefreshToken(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    revoked = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"

    def __str__(self):
        return f"RefreshToken({self.user.username}, revoked={self.revoked})"
