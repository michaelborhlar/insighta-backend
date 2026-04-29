import uuid
from django.db import models


def generate_uuid7():
    try:
        import uuid7 as _uuid7
        return str(_uuid7.uuid7())
    except ImportError:
        return str(uuid.uuid4())


class Profile(models.Model):
    AGE_GROUPS = ["child", "teenager", "adult", "senior"]

    id = models.CharField(primary_key=True, max_length=36, default=generate_uuid7)
    name = models.CharField(max_length=255, unique=True)
    gender = models.CharField(max_length=16)
    gender_probability = models.FloatField()
    age = models.IntegerField()
    age_group = models.CharField(max_length=16)
    country_id = models.CharField(max_length=2)
    country_name = models.CharField(max_length=255)
    country_probability = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "profiles"
        indexes = [
            models.Index(fields=["gender"]),
            models.Index(fields=["age_group"]),
            models.Index(fields=["country_id"]),
            models.Index(fields=["age"]),
            models.Index(fields=["gender_probability"]),
            models.Index(fields=["country_probability"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "gender_probability": self.gender_probability,
            "age": self.age,
            "age_group": self.age_group,
            "country_id": self.country_id,
            "country_name": self.country_name,
            "country_probability": self.country_probability,
            "created_at": self.created_at.isoformat(),
        }
