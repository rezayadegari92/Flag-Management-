from rest_framework import serializers
from django.db import transaction
from .utils import _detect_cycle
from .models import Flag, Dependency, AuditLog


from rest_framework import serializers

class FlagCreateSerializer(serializers.ModelSerializer):
    dependencies = serializers.ListField(
        child=serializers.CharField(),  
        write_only=True,
        required=False
    )

    class Meta:
        model = Flag
        fields = ['id', 'name', 'description', 'dependencies', 'is_active']

    def validate_dependencies(self, value):
        deps = Flag.objects.filter(name__in=value)
        if len(deps) != len(value):
            missing = set(value) - set(deps.values_list('name', flat=True))
            raise serializers.ValidationError(f"Flags not found: {missing}")
        return deps

    def create(self, validated_data):
        deps = validated_data.pop('dependencies', [])
        with transaction.atomic():
            flag = Flag.objects.create(**validated_data)
            for dep_flag in deps:
                if _detect_cycle(flag.id, dep_flag.id):
                    raise serializers.ValidationError(f"Circular dependency detected: {flag.name} -> {dep_flag.name}")
                Dependency.objects.create(flag=flag, dependency_on=dep_flag)
            AuditLog.objects.create(
                flag=flag,
                action='CREATE',
                actor=self.context['request'].user.username if self.context['request'].user.is_authenticated else 'anonymous',
                reason='Flag created'
            )
            return flag

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['dependencies'] = [dep.dependency_on.name for dep in instance.dependencies_as_child.all()]
        return data

class DependencySerializer(serializers.ModelSerializer):
    dependency_on = serializers.CharField(source='dependency_on.name')

    class Meta:
        model = Dependency
        fields = ['dependency_on']

class FlagDetailSerializer(serializers.ModelSerializer):
    dependencies = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()

    class Meta:
        model = Flag
        fields = ['id', 'name', 'description', 'is_active', 'dependencies']

    def get_dependencies(self, obj):
        deps = Dependency.objects.filter(flag=obj).select_related('dependency_on')
        return [d.dependency_on.name for d in deps]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'timestamp', 'actor', 'reason', 'old_status', 'new_status']   



        