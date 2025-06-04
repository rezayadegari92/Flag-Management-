from django.urls import path
from rest_framework import generics
from .models import Flag, AuditLog
from .serializers import FlagCreateSerializer, FlagDetailSerializer
from .views import FlagToggleAPIView, FlagAuditLogAPIView, FlagListCreateAPIView

urlpatterns = [
    path('flags/', generics.ListCreateAPIView.as_view(
        queryset=Flag.objects.all(),
        serializer_class=FlagCreateSerializer  
    ), name='flag-list-create'),
    path('flags/<int:pk>/', generics.RetrieveAPIView.as_view(
        queryset=Flag.objects.all(),
        serializer_class=FlagDetailSerializer
    ), name='flag-detail'),
    path('flags/<int:pk>/toggle/', FlagToggleAPIView.as_view(), name='flag-toggle'),
    path('flags/<int:pk>/audit/', FlagAuditLogAPIView.as_view(), name='flag-audit'),
    path('flags/', FlagListCreateAPIView.as_view(), name='flag-list-create'),
]   