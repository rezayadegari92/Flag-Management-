from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from ..models import FeatureFlag, AuditLog


class FeatureFlagTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create some test flags
        self.flag1 = FeatureFlag.objects.create(
            name='flag1',
            description='First flag',
            is_active=True
        )
        self.flag2 = FeatureFlag.objects.create(
            name='flag2',
            description='Second flag',
            is_active=False
        )
        self.flag3 = FeatureFlag.objects.create(
            name='flag3',
            description='Third flag',
            is_active=False
        )

    def test_create_feature_flag(self):
        """Test creating a new feature flag."""
        url = reverse('flag-list')
        data = {
            'name': 'new_flag',
            'description': 'A new flag',
            'dependencies': [self.flag1.id]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FeatureFlag.objects.count(), 4)
        self.assertEqual(AuditLog.objects.count(), 1)  # Only one audit log for create

        # Verify audit log
        audit_log = AuditLog.objects.latest('created_at')
        self.assertEqual(audit_log.action, 'CREATE')
        self.assertEqual(audit_log.actor, 'system')
        self.assertEqual(audit_log.reason, 'Created feature flag')

    def test_create_flag_with_circular_dependency(self):
        """Test that circular dependencies are detected."""
        url = reverse('flag-list')
        
        # First create a flag that depends on flag1
        data = {
            'name': 'new_flag',
            'description': 'A new flag',
            'dependencies': [self.flag1.id]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_flag = FeatureFlag.objects.get(name='new_flag')

        # Now try to make flag1 depend on new_flag (creating a cycle)
        url = reverse('flag-detail', args=[self.flag1.id])
        data = {
            'dependencies': [new_flag.id]
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data['dependencies'])
        self.assertEqual(response.data['dependencies']['error'], 'Circular dependency detected')

    def test_toggle_flag_on_with_inactive_dependencies(self):
        """Test that a flag cannot be enabled if its dependencies are inactive."""
        # Make flag2 depend on flag3 (which is inactive)
        self.flag2.dependencies.add(self.flag3)
        
        url = reverse('flag-toggle', args=[self.flag2.id])
        data = {
            'actor': 'test_user',
            'reason': 'Testing toggle'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Missing active dependencies')
        self.assertIn('flag3', response.data['missing_dependencies'])

    def test_toggle_flag_on_with_active_dependencies(self):
        """Test that a flag can be enabled if all dependencies are active."""
        # Make flag2 depend on flag1 (which is active)
        self.flag2.dependencies.add(self.flag1)
        
        url = reverse('flag-toggle', args=[self.flag2.id])
        data = {
            'actor': 'test_user',
            'reason': 'Testing toggle'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.flag2.refresh_from_db()
        self.assertTrue(self.flag2.is_active)

        # Verify audit log
        audit_log = AuditLog.objects.latest('created_at')
        self.assertEqual(audit_log.action, 'TOGGLE')
        self.assertEqual(audit_log.actor, 'test_user')
        self.assertEqual(audit_log.reason, 'Testing toggle')

    def test_toggle_flag_off_with_dependents(self):
        """Test that disabling a flag cascades to its dependents."""
        # Make flag2 depend on flag1
        self.flag2.dependencies.add(self.flag1)
        # Make flag3 depend on flag2
        self.flag3.dependencies.add(self.flag2)
        
        # Enable all flags
        self.flag2.is_active = True
        self.flag2.save()
        self.flag3.is_active = True
        self.flag3.save()

        # Now disable flag1
        url = reverse('flag-toggle', args=[self.flag1.id])
        data = {
            'actor': 'test_user',
            'reason': 'Testing cascade disable'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all flags are disabled
        self.flag1.refresh_from_db()
        self.flag2.refresh_from_db()
        self.flag3.refresh_from_db()
        self.assertFalse(self.flag1.is_active)
        self.assertFalse(self.flag2.is_active)
        self.assertFalse(self.flag3.is_active)

        # Verify audit logs
        audit_logs = AuditLog.objects.filter(
            action__in=['TOGGLE', 'AUTO_DISABLE']
        ).order_by('created_at')
        self.assertEqual(audit_logs.count(), 3)  # One TOGGLE and two AUTO_DISABLE

        # First log should be the manual toggle
        self.assertEqual(audit_logs[0].action, 'TOGGLE')
        self.assertEqual(audit_logs[0].actor, 'test_user')
        
        # Next two should be auto-disables
        self.assertEqual(audit_logs[1].action, 'AUTO_DISABLE')
        self.assertEqual(audit_logs[2].action, 'AUTO_DISABLE')
        self.assertEqual(set(log.actor for log in audit_logs[1:]), {'system'})

    def test_toggle_flag_off_with_circular_dependencies(self):
        """Test that disabling a flag with circular dependencies is handled safely."""
        # Create a circular dependency: flag1 -> flag2 -> flag3 -> flag1
        self.flag1.dependencies.add(self.flag2)
        self.flag2.dependencies.add(self.flag3)
        self.flag3.dependencies.add(self.flag1)
        
        # Enable all flags
        self.flag1.is_active = True
        self.flag1.save()
        self.flag2.is_active = True
        self.flag2.save()
        self.flag3.is_active = True
        self.flag3.save()

        # Now disable flag1
        url = reverse('flag-toggle', args=[self.flag1.id])
        data = {
            'actor': 'test_user',
            'reason': 'Testing cascade disable with circular dependencies'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all flags are disabled
        self.flag1.refresh_from_db()
        self.flag2.refresh_from_db()
        self.flag3.refresh_from_db()
        self.assertFalse(self.flag1.is_active)
        self.assertFalse(self.flag2.is_active)
        self.assertFalse(self.flag3.is_active)

        # Verify audit logs - should have exactly one log per flag
        audit_logs = AuditLog.objects.filter(
            action__in=['TOGGLE', 'AUTO_DISABLE']
        ).order_by('created_at')
        self.assertEqual(audit_logs.count(), 3)  # One TOGGLE and two AUTO_DISABLE

        # First log should be the manual toggle of flag1
        self.assertEqual(audit_logs[0].action, 'TOGGLE')
        self.assertEqual(audit_logs[0].flag, self.flag1)
        self.assertEqual(audit_logs[0].actor, 'test_user')
        
        # Next two should be auto-disables of flag2 and flag3
        self.assertEqual(audit_logs[1].action, 'AUTO_DISABLE')
        self.assertEqual(audit_logs[2].action, 'AUTO_DISABLE')
        self.assertEqual(set(log.flag for log in audit_logs[1:]), {self.flag2, self.flag3})
        self.assertEqual(set(log.actor for log in audit_logs[1:]), {'system'})


class AuditLogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.flag = FeatureFlag.objects.create(
            name='test_flag',
            description='Test flag'
        )
        # Create some audit logs
        AuditLog.objects.create(
            flag=self.flag,
            action='CREATE',
            actor='system',
            reason='Created feature flag'
        )
        AuditLog.objects.create(
            flag=self.flag,
            action='TOGGLE',
            actor='test_user',
            reason='Testing toggle'
        )

    def test_list_audit_logs(self):
        """Test retrieving audit logs."""
        url = reverse('audit-log')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Verify logs are ordered by timestamp descending
        self.assertEqual(response.data[0]['action'], 'TOGGLE')
        self.assertEqual(response.data[1]['action'], 'CREATE')

    def test_filter_audit_logs_by_flag(self):
        """Test filtering audit logs by flag name."""
        url = reverse('audit-log')
        response = self.client.get(url, {'flag': 'test_flag'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Test with non-existent flag
        response = self.client.get(url, {'flag': 'non_existent'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0) 