from rest_framework import serializers
from .models import FeatureFlag, AuditLog


class FeatureFlagSerializer(serializers.ModelSerializer):
    dependencies = serializers.PrimaryKeyRelatedField(
        queryset=FeatureFlag.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = FeatureFlag
        fields = ['id', 'name', 'description', 'is_active', 'dependencies', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at']

    def validate_dependencies(self, value):
        """Validate that no circular dependencies are introduced."""
        if not value:
            return value

        instance = getattr(self, 'instance', None)
        # The flag being created or updated
        flag_self = instance if instance else None

        # For each dependency, check if adding it would create a cycle
        for dep in value:
            if self._would_create_cycle(flag_self, dep):
                raise serializers.ValidationError({
                    "error": "Circular dependency detected",
                    "details": f"Adding dependency would create a cycle involving '{dep.name}'"
                })
        return value

    def _would_create_cycle(self, flag_self, dep):
        """Check if adding dep as a dependency to flag_self would create a cycle."""
        if not flag_self:
            # On create, simulate the new flag as the root
            return self._has_path(dep, lambda f: False, set(), creating_flag=True)
        return self._has_path(dep, lambda f: f == flag_self, set())

    def _has_path(self, flag, is_target, visited, creating_flag=False):
        """DFS to see if is_target(flag) is True in the dependency graph."""
        if is_target(flag):
            return True
        if flag in visited:
            return False
        visited.add(flag)
        for dep in flag.dependencies.all():
            if self._has_path(dep, is_target, visited):
                return True
        return False

    def create(self, validated_data):
        # Set is_active to False by default
        validated_data['is_active'] = False
        flag = super().create(validated_data)
        
        # Create initial audit log
        AuditLog.objects.create(
            flag=flag,
            action='CREATE',
            actor='system',
            reason='Created feature flag'
        )
        return flag


class AuditLogSerializer(serializers.ModelSerializer):
    flag = serializers.SlugRelatedField(
        slug_field='name',
        queryset=FeatureFlag.objects.all()
    )

    class Meta:
        model = AuditLog
        fields = ['id', 'flag', 'action', 'actor', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at'] 