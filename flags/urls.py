from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeatureFlagViewSet, AuditLogListAPIView

router = DefaultRouter()
router.register(r'flags', FeatureFlagViewSet, basename='flag')

urlpatterns = [
    path('', include(router.urls)),
    path('audit/', AuditLogListAPIView.as_view(), name='audit-log'),
] 