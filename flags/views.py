from django.shortcuts import render
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import FeatureFlag, AuditLog
from .serializers import FeatureFlagSerializer, AuditLogSerializer


class FeatureFlagViewSet(viewsets.ModelViewSet):
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    http_method_names = ['get', 'post', 'patch']  # Allow list, create, retrieve, and update

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, pk=None):
        flag = self.get_object()
        actor = request.data.get('actor')
        reason = request.data.get('reason')

        if not actor or not reason:
            return Response(
                {"error": "actor and reason are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If flag is inactive and we're trying to enable it
        if not flag.is_active:
            # Check all dependencies are active
            inactive_deps = flag.dependencies.filter(is_active=False)
            if inactive_deps.exists():
                return Response({
                    "error": "Missing active dependencies",
                    "missing_dependencies": [dep.name for dep in inactive_deps]
                }, status=status.HTTP_400_BAD_REQUEST)

            # Enable the flag
            flag.is_active = True
            flag.save()
            AuditLog.objects.create(
                flag=flag,
                action='TOGGLE',
                actor=actor,
                reason=reason
            )
            return Response(self.get_serializer(flag).data)

        # If flag is active and we're trying to disable it
        else:
            # First disable this flag
            flag.is_active = False
            flag.save()
            AuditLog.objects.create(
                flag=flag,
                action='TOGGLE',
                actor=actor,
                reason=reason
            )

            # Find all dependent flags that need to be disabled
            cascade_disabled = []
            self._disable_dependents(flag, cascade_disabled)

            return Response({
                "disabled_flag": flag.name,
                "cascade_disabled": cascade_disabled
            })

    def _disable_dependents(self, flag, cascade_disabled, visited=None):
        """Recursively disable all dependent flags, avoiding circular dependencies.
        
        Args:
            flag: The flag being disabled
            cascade_disabled: List to track disabled flags
            visited: Set of flag IDs that have already been processed
        """
        if visited is None:
            visited = set()

        # Skip if we've already processed this flag
        if flag.id in visited:
            return

        # Mark this flag as visited
        visited.add(flag.id)

        # Get all flags that directly depend on this flag
        direct_dependents = FeatureFlag.objects.filter(
            dependencies=flag,
            is_active=True
        )

        for dependent in direct_dependents:
            # Skip if we've already processed this dependent
            if dependent.id in visited:
                continue

            # Disable the dependent
            dependent.is_active = False
            dependent.save()
            cascade_disabled.append(dependent.name)

            # Create audit log
            AuditLog.objects.create(
                flag=dependent,
                action='AUTO_DISABLE',
                actor='system',
                reason=f'Dependency {flag.name} was disabled'
            )

            # Recursively disable its dependents
            self._disable_dependents(dependent, cascade_disabled, visited)


class AuditLogListAPIView(APIView):
    def get(self, request):
        queryset = AuditLog.objects.all().order_by('-created_at')
        
        # Optional filtering
        flag_name = request.query_params.get('flag')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if flag_name:
            queryset = queryset.filter(flag__name=flag_name)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        serializer = AuditLogSerializer(queryset, many=True)
        return Response(serializer.data)
