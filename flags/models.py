from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class FeatureFlag(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True)

    def __str__(self):
        return self.name


class AuditLog(TimeStampedModel):
    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='logs')
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('TOGGLE', 'Toggle'),
        ('AUTO_DISABLE', 'Auto Disable'),
    ]
    action = models.CharField(max_length=255, choices=ACTION_CHOICES)
    actor = models.CharField(max_length=255)
    reason = models.TextField()

    def __str__(self):
        return f"{self.flag.name} - {self.action} - {self.actor}"
