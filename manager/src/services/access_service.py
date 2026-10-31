# manager/src/services/access_service.py

import logging
from typing import List, Dict, Optional, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from collections import defaultdict

from manager.src.db import models
from manager.src.auth.models import User  # noqa: F401  # BUG-102: Finding.reviewer -> User
from manager.src.connectors.permissions import PermissionCollectorFactory
from manager.src.services.access_config import get_access_config

logger = logging.getLogger(__name__)


class AccessService:
    """
    Сервис управления доступом
    
    Поддерживает два режима:
    - local: сбор прав через icacls на Manager
    - remote: сбор прав через API Scanner
    
    Режим выбирается через конфигурацию (access_config.json)
    """
    
    ADMIN_PRINCIPALS = {'administrator', 'system', 'domain admins', 'enterprise admins'}
    HIGH_RISK_PERMISSIONS = {'full_control', 'modify'}
    MEDIUM_RISK_PERMISSIONS = {'write', 'delete'}
    LOW_RISK_PERMISSIONS = {'read', 'execute'}
    
    def __init__(self, db: Session, collector_type: Optional[str] = None):
        """
        Инициализация сервиса
        
        Args:
            db: Сессия БД
            collector_type: Тип коллектора (local или remote).
                           Если не указан — берется из конфига.
        """
        self.db = db
        self.config = get_access_config()
        self.collector_type = collector_type or self.config.mode
        
        # Создаем коллектор через фабрику
        self.collector = PermissionCollectorFactory.get_collector(
            self.collector_type
        )
        logger.info(f"AccessService initialized with collector: {self.collector_type}")
    
    def get_current_mode(self) -> str:
        """Получить текущий режим работы"""
        return self.collector_type
    
    def get_available_modes(self) -> dict:
        """Получить список доступных режимов"""
        return PermissionCollectorFactory.get_available_collectors()
    
    def switch_mode(self, new_mode: str) -> None:
        """
        Переключить режим сбора прав
        
        Args:
            new_mode: "local", "ad", "mixed" или "remote"
        """
        if new_mode not in ["local", "remote", "ad", "mixed"]:
            raise ValueError(f"Unknown mode: {new_mode}")
        
        self.collector_type = new_mode
        self.collector = PermissionCollectorFactory.get_collector(new_mode)
        logger.info(f"Switched to mode: {new_mode}")
    
    # ============================================================
    # 1. Синхронизация прав
    # ============================================================
    
    def sync_permissions(self, resource_id: int, force: bool = False) -> Dict[str, Any]:
        """
        Синхронизировать права доступа для ресурса
        
        Args:
            resource_id: ID ресурса
            force: Принудительная синхронизация (игнорировать кэш)
            
        Returns:
            Dict: Статистика синхронизации
        """
        logger.info(f"Syncing permissions for resource_id={resource_id} (mode: {self.collector_type})")
        
        resource = self.db.query(models.Resource).filter(models.Resource.id == resource_id).first()
        if not resource:
            raise ValueError(f"Resource with id {resource_id} not found")
        if not resource.path:
            raise ValueError(f"Resource {resource_id} has no path")
        
        if not self.collector.is_available():
            raise RuntimeError(f"Collector '{self.collector_type}' is not available")
        
        try:
            raw_entries = self.collector.collect(resource.path)
            logger.info(f"Collected {len(raw_entries)} permission entries")
            
            # Удалить старые записи
            deleted = self.db.query(models.AccessEntry).filter(
                models.AccessEntry.resource_id == resource_id
            ).delete()
            logger.info(f"Deleted {deleted} old permission entries")
            
            saved = 0
            for raw_entry in raw_entries:
                access_entry = self._create_access_entry(resource_id, raw_entry)
                self.db.add(access_entry)
                saved += 1
            
            resource.permission_last_synced = datetime.utcnow()
            self.db.commit()
            logger.info(f"Saved {saved} new permission entries")
            
            alerts_generated = 0
            if self.config.alerts_enabled:
                alerts_generated = self._generate_alerts(resource_id)
            
            return {
                "resource_id": resource_id,
                "path": resource.path,
                "entries_collected": len(raw_entries),
                "entries_saved": saved,
                "alerts_generated": alerts_generated,
                "synced_at": resource.permission_last_synced.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during sync: {e}", exc_info=True)
            raise RuntimeError(f"Failed to sync permissions: {e}")
    
    def _create_access_entry(self, resource_id: int, raw_entry: Dict) -> models.AccessEntry:
        return models.AccessEntry(
            resource_id=resource_id,
            principal_type=raw_entry.get('principal_type', 'unknown'),
            principal_name=raw_entry.get('principal', ''),
            principal_sid=raw_entry.get('principal_sid'),
            principal_domain=raw_entry.get('principal_domain'),
            principal_upn=raw_entry.get('principal_upn'),
            permission_type=self._normalize_permission(
                raw_entry.get('permissions', ['unknown'])[0]
            ),
            permission_source=raw_entry.get('permission_source', 'direct'),
            inherited_from=raw_entry.get('inherited_from'),
            is_inherited=raw_entry.get('is_inherited', False),
            granted_at=datetime.utcnow(),
            granted_by=None,
            last_verified_at=datetime.utcnow(),
            is_active=True,
            collector_source=raw_entry.get('collector_source', self.collector_type)
        )
    
    # ============================================================
    # 2. Эффективные права
    # ============================================================
    
    def get_effective_permissions(self, resource_id: int, principal: str) -> List[str]:
        """Получить эффективные права для пользователя"""
        logger.debug(f"Getting effective permissions for {principal} on resource {resource_id}")
        
        resource = self.db.query(models.Resource).filter(models.Resource.id == resource_id).first()
        if not resource:
            raise ValueError(f"Resource with id {resource_id} not found")
        
        entries = self.db.query(models.AccessEntry).filter(
            and_(
                models.AccessEntry.resource_id == resource_id,
                models.AccessEntry.is_active == True
            )
        ).all()
        
        if not entries:
            return []
        
        principal_normalized = principal.lower()
        permissions = set()
        
        for entry in entries:
            entry_principal = entry.principal_name.lower()
            if entry_principal == principal_normalized:
                permissions.add(entry.permission_type)
                continue
            
            groups = self.collector.get_principal_groups(principal)
            for group in groups:
                if group.lower() == entry_principal:
                    permissions.add(entry.permission_type)
                    break
            
            if self._is_admin_principal(principal) and 'administrators' in entry_principal:
                permissions.add(entry.permission_type)
        
        return list(permissions)
    
    def get_effective_permissions_detailed(self, resource_id: int, principal: str) -> Dict[str, Any]:
        """Получить эффективные права с деталями"""
        resource = self.db.query(models.Resource).filter(models.Resource.id == resource_id).first()
        if not resource:
            raise ValueError(f"Resource with id {resource_id} not found")
        
        entries = self.db.query(models.AccessEntry).filter(
            and_(
                models.AccessEntry.resource_id == resource_id,
                models.AccessEntry.is_active == True
            )
        ).all()
        
        if not entries:
            return {"principal": principal, "permissions": [], "sources": []}
        
        principal_normalized = principal.lower()
        permissions = set()
        sources = []
        
        for entry in entries:
            entry_principal = entry.principal_name.lower()
            matched = False
            
            if entry_principal == principal_normalized:
                matched = True
            
            if not matched:
                groups = self.collector.get_principal_groups(principal)
                for group in groups:
                    if group.lower() == entry_principal:
                        matched = True
                        break
            
            if not matched and self._is_admin_principal(principal):
                if 'administrators' in entry_principal or 'system' in entry_principal:
                    matched = True
            
            if matched:
                permissions.add(entry.permission_type)
                sources.append({
                    "permission": entry.permission_type,
                    "source": entry.principal_name,
                    "inherited": entry.is_inherited,
                    "source_type": entry.principal_type
                })
        
        return {
            "principal": principal,
            "permissions": list(permissions),
            "sources": sources
        }
    
    # ============================================================
    # 3. Анализ избыточных прав
    # ============================================================
    
    def find_excessive_permissions(self, resource_id: int) -> List[Dict]:
        """Найти избыточные права"""
        logger.info(f"Finding excessive permissions for resource {resource_id}")
        
        resource = self.db.query(models.Resource).filter(models.Resource.id == resource_id).first()
        if not resource:
            raise ValueError(f"Resource with id {resource_id} not found")
        
        entries = self.db.query(models.AccessEntry).filter(
            and_(
                models.AccessEntry.resource_id == resource_id,
                models.AccessEntry.is_active == True
            )
        ).all()
        
        issues = []
        threshold = self.config.excessive_days_threshold
        
        for entry in entries:
            if self._is_admin_principal(entry.principal_name):
                continue
            
            # Правило 1: Полный доступ у обычных пользователей
            if entry.permission_type == 'full_control' and entry.principal_type in ['user', 'local_user']:
                issues.append({
                    "type": "excessive_permission",
                    "severity": "warning",
                    "principal": entry.principal_name,
                    "permission": "full_control",
                    "description": f"Пользователь {entry.principal_name} имеет полный доступ",
                    "recommendation": "Замените полный доступ на минимально необходимый (чтение/запись)",
                    "resource_id": resource_id
                })
            
            # Правило 2: Права старше N дней без проверки
            if entry.last_verified_at and (datetime.utcnow() - entry.last_verified_at) > timedelta(days=threshold):
                days_old = (datetime.utcnow() - entry.last_verified_at).days
                issues.append({
                    "type": "stale_permission",
                    "severity": "info",
                    "principal": entry.principal_name,
                    "permission": entry.permission_type,
                    "description": f"Права не проверялись {days_old} дней (порог {threshold})",
                    "recommendation": "Проверьте необходимость прав, возможно, пользователь уже не работает с данными",
                    "resource_id": resource_id
                })
            
            # Правило 3: Чувствительные данные у не-администратора
            if resource.is_sensitive and entry.principal_type in ['user', 'local_user', 'group']:
                if entry.permission_type in ['full_control', 'modify', 'write', 'delete']:
                    issues.append({
                        "type": "sensitive_access",
                        "severity": "critical",
                        "principal": entry.principal_name,
                        "permission": entry.permission_type,
                        "description": f"Чувствительные данные доступны обычному пользователю {entry.principal_name}",
                        "recommendation": "Ограничьте доступ к чувствительным данным только для администраторов",
                        "resource_id": resource_id
                    })
            
            # Правило 4: Широкий доступ для всех
            if 'everyone' in entry.principal_name.lower() or 'authenticated users' in entry.principal_name.lower():
                issues.append({
                    "type": "wide_access",
                    "severity": "warning",
                    "principal": entry.principal_name,
                    "permission": entry.permission_type,
                    "description": f"Широкий доступ для {entry.principal_name}",
                    "recommendation": "Ограничьте доступ только для необходимых пользователей",
                    "resource_id": resource_id
                })
            
            # Правило 5: Неопределенные специальные права
            if entry.permission_type == 'special_access':
                issues.append({
                    "type": "undefined_permission",
                    "severity": "info",
                    "principal": entry.principal_name,
                    "permission": "special_access",
                    "description": f"Неопределенные специальные права для {entry.principal_name}",
                    "recommendation": "Уточните права и замените на конкретные (чтение/запись/модерация)",
                    "resource_id": resource_id
                })
        
        logger.info(f"Found {len(issues)} issues")
        return issues
    
    # ============================================================
    # 4. Анализ наследования
    # ============================================================
    
    def analyze_inheritance(self, resource_id: int) -> Dict[str, Any]:
        """Анализ наследования прав"""
        logger.info(f"Analyzing inheritance for resource {resource_id}")
        
        resource = self.db.query(models.Resource).filter(models.Resource.id == resource_id).first()
        if not resource:
            raise ValueError(f"Resource with id {resource_id} not found")
        
        entries = self.db.query(models.AccessEntry).filter(
            models.AccessEntry.resource_id == resource_id
        ).all()
        
        if not entries:
            return {
                "total_entries": 0,
                "inherited_count": 0,
                "direct_count": 0,
                "inherited_percent": 0.0,
                "inherited_entries": [],
                "potential_issues": ["Нет записей прав доступа"]
            }
        
        total = len(entries)
        inherited = [e for e in entries if e.is_inherited]
        direct = [e for e in entries if not e.is_inherited]
        inherited_percent = (len(inherited) / total) * 100 if total > 0 else 0
        
        inherited_entries = []
        for entry in inherited[:10]:
            inherited_entries.append({
                "principal": entry.principal_name,
                "permission": entry.permission_type,
                "inherited_from": entry.inherited_from or "parent"
            })
        
        potential_issues = []
        if inherited_percent > 70:
            potential_issues.append(
                f"Высокий процент наследуемых прав ({inherited_percent:.1f}%) — возможны избыточные права"
            )
        if inherited_percent < 10 and total > 5:
            potential_issues.append(
                f"Низкий процент наследуемых прав ({inherited_percent:.1f}%) — "
                "возможно, права настраивались вручную без учета иерархии"
            )
        if len(inherited) > 20:
            potential_issues.append(
                f"Много наследуемых записей ({len(inherited)}) — сложно управлять правами"
            )
        
        return {
            "total_entries": total,
            "inherited_count": len(inherited),
            "direct_count": len(direct),
            "inherited_percent": round(inherited_percent, 1),
            "inherited_entries": inherited_entries,
            "potential_issues": potential_issues
        }
    
    # ============================================================
    # 5. Генерация алертов
    # ============================================================
    
    def _generate_alerts(self, resource_id: int) -> int:
        """Генерация алертов (внутренний метод)"""
        logger.info(f"Generating alerts for resource {resource_id}")
        issues = self.find_excessive_permissions(resource_id)
        alerts_count = 0
        
        for issue in issues:
            existing_alert = self.db.query(models.AccessAlert).filter(
                and_(
                    models.AccessAlert.resource_id == resource_id,
                    models.AccessAlert.alert_type == issue['type'],
                    models.AccessAlert.principal_name == issue['principal'],
                    models.AccessAlert.status.in_(['open', 'acknowledged'])
                )
            ).first()
            
            if existing_alert:
                existing_alert.description = issue['description']
                existing_alert.recommendation = issue['recommendation']
                existing_alert.severity = issue['severity']
                # Если нужно обновить время, можно добавить updated_at
                logger.debug(f"Updated alert: {issue['type']} for {issue['principal']}")
            else:
                alert = models.AccessAlert(
                    resource_id=resource_id,
                    alert_type=issue['type'],
                    severity=issue['severity'],
                    principal_name=issue['principal'],
                    description=issue['description'],
                    recommendation=issue['recommendation'],
                    status='open',
                    created_at=datetime.utcnow()
                )
                self.db.add(alert)
                logger.debug(f"Created alert: {issue['type']} for {issue['principal']}")
            
            alerts_count += 1
        
        self.db.commit()
        logger.info(f"Generated/updated {alerts_count} alerts")
        return alerts_count
    
    def generate_alerts(self, resource_id: int) -> int:
        """Публичный метод для генерации алертов"""
        return self._generate_alerts(resource_id)
    
    # ============================================================
    # 6. Получение отчета
    # ============================================================
    
    def get_access_report(self, resource_id: int) -> Dict[str, Any]:
        """Получить полный отчет по доступу"""
        logger.info(f"Generating access report for resource {resource_id}")
        
        resource = self.db.query(models.Resource).filter(models.Resource.id == resource_id).first()
        if not resource:
            raise ValueError(f"Resource with id {resource_id} not found")
        
        entries = self.db.query(models.AccessEntry).filter(
            models.AccessEntry.resource_id == resource_id
        ).all()
        
        total = len(entries)
        users = sum(1 for e in entries if e.principal_type in ['user', 'local_user'])
        groups = sum(1 for e in entries if e.principal_type in ['group', 'ad_group'])
        system = sum(1 for e in entries if e.principal_type == 'system')
        inherited = sum(1 for e in entries if e.is_inherited)
        
        permissions_by_type = defaultdict(int)
        for entry in entries:
            permissions_by_type[entry.permission_type] += 1
        
        excessive = self.find_excessive_permissions(resource_id)
        inheritance = self.analyze_inheritance(resource_id)
        
        alerts = self.db.query(models.AccessAlert).filter(
            models.AccessAlert.resource_id == resource_id
        ).all()
        alerts_stats = {
            "total": len(alerts),
            "critical": sum(1 for a in alerts if a.severity == 'critical' and a.status == 'open'),
            "warning": sum(1 for a in alerts if a.severity == 'warning' and a.status == 'open'),
            "info": sum(1 for a in alerts if a.severity == 'info' and a.status == 'open')
        }
        
        principal_perms = defaultdict(set)
        for entry in entries:
            principal_perms[entry.principal_name].add(entry.permission_type)
        top_principals = []
        for principal, perms in sorted(principal_perms.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            top_principals.append({
                "principal": principal,
                "permissions": list(perms),
                "is_inherited": any(e.is_inherited for e in entries if e.principal_name == principal)
            })
        
        return {
            "resource": {
                "id": resource.id,
                "path": resource.path,
                "is_sensitive": resource.is_sensitive,
                "classification_level": resource.classification_level,
                "last_synced": resource.permission_last_synced.isoformat() if resource.permission_last_synced else None
            },
            "permissions_summary": {
                "total": total,
                "users": users,
                "groups": groups,
                "system": system,
                "inherited": inherited
            },
            "permissions_by_type": dict(permissions_by_type),
            "excessive_permissions": excessive,
            "inheritance_analysis": inheritance,
            "alerts": alerts_stats,
            "top_principals": top_principals
        }
    
    # ============================================================
    # 7. Вспомогательные методы
    # ============================================================
    
    def _normalize_permission(self, permission: str) -> str:
        if not permission:
            return 'unknown'
        mapping = {
            'f': 'full_control', 'full': 'full_control', 'full control': 'full_control',
            'r': 'read', 'read': 'read',
            'w': 'write', 'write': 'write',
            'm': 'modify', 'modify': 'modify',
            'd': 'delete', 'delete': 'delete',
            'x': 'execute', 'execute': 'execute',
            'rx': 'read_execute', 'read_execute': 'read_execute',
            'special': 'special_access', 'special_access': 'special_access'
        }
        return mapping.get(permission.lower().strip(), permission.lower().strip())
    
    def _is_admin_principal(self, principal: str) -> bool:
        if not principal:
            return False
        principal_lower = principal.lower()
        for admin in self.ADMIN_PRINCIPALS:
            if admin in principal_lower:
                return True
        if 'builtin\\administrators' in principal_lower:
            return True
        if 'nt authority\\system' in principal_lower:
            return True
        if 'domain admins' in principal_lower:
            return True
        return False
    
    # ============================================================
    # 8. Дополнительные методы для интеграции
    # ============================================================
    
    def get_resource_permissions(self, resource_id: int) -> List[Dict]:
        entries = self.db.query(models.AccessEntry).filter(
            models.AccessEntry.resource_id == resource_id
        ).all()
        return [entry.to_dict() for entry in entries]
    
    def get_alerts(self, resource_id: int = None, status: str = None) -> List[Dict]:
        query = self.db.query(models.AccessAlert)
        if resource_id:
            query = query.filter(models.AccessAlert.resource_id == resource_id)
        if status:
            query = query.filter(models.AccessAlert.status == status)
        alerts = query.order_by(models.AccessAlert.created_at.desc()).all()
        return [alert.to_dict() for alert in alerts]
    
    def resolve_alert(self, alert_id: int, resolved_by: str) -> bool:
        alert = self.db.query(models.AccessAlert).filter(models.AccessAlert.id == alert_id).first()
        if not alert:
            return False
        alert.status = 'resolved'
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = resolved_by
        self.db.commit()
        logger.info(f"Alert {alert_id} resolved by {resolved_by}")
        return True
    
    def acknowledge_alert(self, alert_id: int) -> bool:
        alert = self.db.query(models.AccessAlert).filter(models.AccessAlert.id == alert_id).first()
        if not alert:
            return False
        alert.status = 'acknowledged'
        self.db.commit()
        logger.info(f"Alert {alert_id} acknowledged")
        return True
    
    def get_permission_trends(self, resource_id: int, days: int = 30) -> Dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)
        changes = self.db.query(models.PermissionChange).filter(
            and_(
                models.PermissionChange.resource_id == resource_id,
                models.PermissionChange.changed_at >= since
            )
        ).all()
        return {
            "period_days": days,
            "total_changes": len(changes),
            "by_type": {
                "grant": sum(1 for c in changes if c.change_type == 'grant'),
                "revoke": sum(1 for c in changes if c.change_type == 'revoke'),
                "modify": sum(1 for c in changes if c.change_type == 'modify')
            },
            "most_active_principals": [
                {
                    "principal": c.principal_name,
                    "changes": sum(1 for ch in changes if ch.principal_name == c.principal_name)
                }
                for c in changes[:5]
            ] if changes else []
        }