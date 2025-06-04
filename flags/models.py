from django.db import models




class Flag(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Dependency(models.Model):
    flag = models.ForeignKey(Flag, on_delete=models.CASCADE, related_name='dependencies_as_child')
    dependency_on = models.ForeignKey(Flag, on_delete=models.CASCADE, related_name='dependencies_as_parent')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('flag', 'dependency_on')

    def __str__(self):
        return f"{self.flag.name} depends on {self.dependency_on.name}"
        

class AuditLog(models.Model):
    flag = models.ForeignKey(Flag, on_delete=models.CASCADE, related_name='audit_logs')
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('TOGGLE', 'Toggle'),
        ('AUTO_DISABLE', 'Auto Disable'),
    ]
    action = models.CharField(max_length=255, choices=ACTION_CHOICES)
    actor = models.CharField(max_length=255)
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    old_status = models.BooleanField(default=False)
    new_status = models.BooleanField(default=False)

    def __str__(self):
        return f"[{self.timestamp}] {self.actor} - {self.action} on {self.flag.name}"
