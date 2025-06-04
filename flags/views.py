from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .utils import get_inactive_direct_dependencies, cascade_disable
from .models import Flag, AuditLog
from .serializers import AuditLogSerializer, FlagCreateSerializer, FlagDetailSerializer
from rest_framework import generics
from django.shortcuts import render

def api_docs(request):
    return render(request, 'api_docs.html')

class FlagToggleAPIView(APIView):
    permission_classes = [permissions.AllowAny]  

    def patch(self, request, pk):
        
        try:
            flag = Flag.objects.get(pk=pk)
        except Flag.DoesNotExist:
            return Response({"error": "Flag not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('active')
        reason = request.data.get('reason', '')
        actor = request.data.get('actor', 'anonymous')

        if new_status not in [True, False]:
            return Response({"error": "Invalid 'active' value."}, status=status.HTTP_400_BAD_REQUEST)

        
        if new_status and not flag.is_active:
            missing = get_inactive_direct_dependencies(flag)
            if missing:
                return Response(
                    {"error": "Missing active dependencies", "missing_dependencies": missing},
                    status=status.HTTP_409_CONFLICT
                )
            
            old = flag.is_active
            flag.is_active = True
            flag.save(update_fields=['is_active', 'updated_at'])
           
            AuditLog.objects.create(
                flag=flag,
                action='toggle',
                actor=actor,
                reason=reason,
                old_status=old,
                new_status=True
            )
            return Response({"status": "activated"}, status=status.HTTP_200_OK)

       
        if not new_status and flag.is_active:
            old = flag.is_active
            flag.is_active = False
            flag.save(update_fields=['is_active', 'updated_at'])
            AuditLog.objects.create(
                flag=flag,
                action='toggle',
                actor=actor,
                reason=reason,
                old_status=old,
                new_status=False
            )
            
            cascade_disable(flag, actor, f"Parent {flag.name} was disabled. {reason}")
            return Response({"status": "deactivated"}, status=status.HTTP_200_OK)

        return Response({"status": "no_change"}, status=status.HTTP_200_OK)

class FlagListCreateAPIView(generics.ListCreateAPIView):
    queryset = Flag.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return FlagCreateSerializer
        return FlagDetailSerializer


class FlagAuditLogAPIView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.AllowAny]
    queryset = AuditLog.objects.all()



class FlagAuditLogAPIView(generics.ListAPIView):
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        flag_id = self.kwargs['pk']
        return AuditLog.objects.filter(flag_id=flag_id).order_by('-timestamp')
