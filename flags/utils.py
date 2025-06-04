from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Flag, Dependency, AuditLog



def _detect_cycle(start_flag_id, dependency_on_id):

    visited = set()

    def dfs(current_id):
        if current_id == start_flag_id:
            return True
        
        visited.add(current_id)
        parents = Dependency.objects.filter(flag_id=current_id).values_list('dependency_on_id', flat=True)
        for parent_id in parents:
            if parent_id in visited:
                
                if dfs(parent_id):
                    return True
        
        return False
    
    return dfs(dependency_on_id)

def get_inactive_direct_dependencies(flag):
    
    deps = Dependency.objects.filter(flag=flag).select_related('depends_on')
    missing = [d.depends_on.name for d in deps if not d.depends_on.active]
    return missing
        

from collections import deque

def cascade_disable(start_flag, actor, reason):
    
    
    queue = deque([start_flag.id])
    visited = set()

    while queue:
        current_id = queue.popleft()
        if current_id in visited:
            continue
        visited.add(current_id)
        dependents = Dependency.objects.filter(depends_on_id=current_id).values_list('flag_id', flat=True)
        for dependent_id in dependents:
            if dependent_id not in visited:

                f = Flag.objects.get(id=dependent_id)
                if f.active:
                    old = f.active
                    f.active = False
                    f.save(update_fields=['active', 'updated_at'])
                    AuditLog.objects.create(
                        flag=f,
                        action='auto_disable',
                        actor=actor,
                        reason=f"Auto-disabled because dependency {start_flag.name} was disabled. {reason}",
                        old_status=old,
                        new_status=False
                    )
                queue.append(dependent_id)          