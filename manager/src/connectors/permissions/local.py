# manager/src/connectors/permissions/local.py

import subprocess
import re
import platform
from typing import List, Dict, Optional
from .base import PermissionCollector


class LocalPermissionCollector(PermissionCollector):
    """Коллектор для Windows 10 (без AD)"""
    
    # Маппинг русских названий → английские
    PRINCIPAL_MAPPING = {
        "Администраторы": "Administrators",
        "СИСТЕМА": "SYSTEM",
        "Прошедшие проверку": "Authenticated Users",
        "Пользователи": "Users",
        "Гости": "Guests",
        "Операторы архива": "Backup Operators",
        "Опытные пользователи": "Power Users",
    }
    
    def __init__(self):
        self._source_type = "local"
        self._available = self._check_availability()
        self._encoding = 'cp866' if platform.system() == 'Windows' else 'utf-8'
    
    def _check_availability(self) -> bool:
        try:
            if platform.system() != 'Windows':
                return False
            subprocess.run(['icacls', '--version'], capture_output=True, timeout=5, shell=True)
            return True
        except:
            return False
    
    def collect(self, resource_path: str) -> List[Dict]:
        if not self.is_available():
            raise RuntimeError("icacls not available on this system")
        if not resource_path:
            raise ValueError("Resource path cannot be empty")
        
        try:
            resource_path = resource_path.replace('/', '\\')
            result = subprocess.run(
                ['icacls', resource_path],
                capture_output=True,
                text=True,
                encoding=self._encoding,
                errors='ignore',
                timeout=30
            )
            if result.returncode != 0 and result.stderr:
                error_msg = result.stderr.strip()
                if "Нет доступа" in error_msg or "Access is denied" in error_msg:
                    raise PermissionError(f"Access denied to {resource_path}")
                elif "не найден" in error_msg or "not found" in error_msg:
                    raise FileNotFoundError(f"Path not found: {resource_path}")
                else:
                    raise RuntimeError(f"icacls error: {error_msg}")
            return self._parse_icacls_output(result.stdout, resource_path)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"icacls timeout for {resource_path}")
        except FileNotFoundError:
            raise RuntimeError("icacls command not found")
        except Exception as e:
            if isinstance(e, (PermissionError, FileNotFoundError)):
                raise
            raise RuntimeError(f"Failed to collect permissions: {e}")
    
    def _parse_icacls_output(self, output: str, resource_path: str) -> List[Dict]:
        """Парсинг вывода icacls (поддержка русского языка)"""
        entries = []
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Пропускаем служебные строки
            if any(line.startswith(x) for x in ['SUCCESS', 'ДОСТУП', 'Обработано', 'Успешно', 'Successfully']):
                continue
            
            # Пропускаем строку с путем
            if resource_path in line:
                continue
            
            # Пропускаем строки с информацией о наследовании
            if 'наследование' in line.lower() or 'inheritance' in line.lower():
                continue
            
            # [OK] КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: игнорируем дублирующие строки с флагами наследования
            # Например: BUILTIN\Администраторы:(I)(OI)(CI)(IO)(F) — это дубликат
            # Оставляем только основную запись: BUILTIN\Администраторы:(I)(F)
            if '(OI)(CI)(IO)' in line or '(OI)(CI)' in line:
                continue
            
            # [OK] Основной паттерн: principal:(flags)permissions
            match = re.match(r'^([^:]+):\(([^)]*)\)([A-Z]+|\([^)]+\))', line)
            if match:
                principal = match.group(1).strip()
                flags = match.group(2).strip() if match.group(2) else ''
                rights_str = match.group(3).strip()
                
                # Если права содержат только флаги — пропускаем
                if rights_str in ['OI', 'CI', 'IO', 'NP']:
                    continue
                
                normalized_principal = self._normalize_principal(principal)
                
                entries.append({
                    "principal": normalized_principal,
                    "principal_type": self._get_principal_type(normalized_principal),
                    "principal_sid": self._get_principal_sid(normalized_principal),
                    "principal_domain": self._get_principal_domain(normalized_principal),
                    "permissions": self._parse_rights(rights_str),
                    "is_inherited": self._is_inherited(flags) or self._is_inherited(rights_str),
                    "inherited_from": self._get_inherited_from(flags),
                    "collector_source": "local"
                })
                continue
            
            # [OK] Альтернативный формат: principal:permissions
            match = re.match(r'^([^:]+):([A-Z]+)$', line)
            if match:
                principal = match.group(1).strip()
                rights = match.group(2).strip()
                
                if rights in ['OI', 'CI', 'IO', 'NP']:
                    continue
                
                normalized_principal = self._normalize_principal(principal)
                
                entries.append({
                    "principal": normalized_principal,
                    "principal_type": self._get_principal_type(normalized_principal),
                    "principal_sid": self._get_principal_sid(normalized_principal),
                    "principal_domain": self._get_principal_domain(normalized_principal),
                    "permissions": self._parse_rights(rights),
                    "is_inherited": False,
                    "inherited_from": None,
                    "collector_source": "local"
                })
                continue
            
            # [OK] Формат: (special access: ...)
            match = re.match(r'^([^:]+):\(special access:([^)]*)\)$', line)
            if match:
                principal = match.group(1).strip()
                special_rights = match.group(2).strip()
                
                normalized_principal = self._normalize_principal(principal)
                
                entries.append({
                    "principal": normalized_principal,
                    "principal_type": self._get_principal_type(normalized_principal),
                    "principal_sid": self._get_principal_sid(normalized_principal),
                    "principal_domain": self._get_principal_domain(normalized_principal),
                    "permissions": self._parse_special_rights(special_rights),
                    "is_inherited": False,
                    "inherited_from": None,
                    "collector_source": "local"
                })
                continue
        
        return entries
    
    def _normalize_principal(self, principal: str) -> str:
        """Нормализовать имя principal (русские названия → английские)"""
        for ru, en in self.PRINCIPAL_MAPPING.items():
            if ru in principal:
                return principal.replace(ru, en)
        return principal
    
    def _parse_rights(self, rights_str: str) -> List[str]:
        """Преобразовать права в список. Игнорирует флаги наследования."""
        if not rights_str:
            return []
        
        # Если это флаги наследования — игнорируем
        if rights_str in ['OI', 'CI', 'IO', 'NP']:
            return []
        
        # Если это (GR,GE) или подобное — убираем скобки
        if rights_str.startswith('(') and rights_str.endswith(')'):
            rights_str = rights_str[1:-1]
        
        # Обработка списка прав через запятую: (GR,GE) → GR, GE
        if ',' in rights_str:
            parts = [p.strip() for p in rights_str.split(',') if p.strip()]
            result = []
            for part in parts:
                if part in ['OI', 'CI', 'IO', 'NP']:
                    continue
                result.extend(self._parse_rights(part))
            return list(set(result))
        
        # Карта прав
        mapping = {
            'F': ['full_control'],
            'R': ['read'],
            'W': ['write'],
            'D': ['delete'],
            'M': ['modify'],
            'RX': ['read', 'execute'],
            'WX': ['write', 'execute'],
            'RC': ['read', 'create'],
            'WD': ['write', 'delete'],
            'WO': ['write_owner'],
            'GR': ['generic_read'],
            'GW': ['generic_write'],
            'GX': ['generic_execute'],
            'G': ['generic_all'],
            'N': ['no_access'],
            'P': ['change_permissions'],
            'T': ['take_ownership'],
            'RCS': ['read_control'],
            'WDA': ['write_dac'],
            'WOW': ['write_owner'],
            'S': ['synchronize'],
        }
        
        # Если несколько букв (например, "RWX")
        if len(rights_str) > 1 and all(c.isalpha() for c in rights_str):
            result = []
            for char in rights_str:
                if char in mapping:
                    result.extend(mapping[char])
            return list(set(result)) if result else [rights_str.lower()]
        
        return mapping.get(rights_str, [rights_str.lower()])
    
    def _parse_special_rights(self, rights_str: str) -> List[str]:
        rights = []
        if not rights_str:
            return rights
        
        special_map = {
            'READ': 'read',
            'WRITE': 'write',
            'DELETE': 'delete',
            'MODIFY': 'modify',
            'FULL': 'full_control',
            'APPEND': 'append',
            'EXECUTE': 'execute',
            'READ_ATTRIBUTES': 'read_attributes',
            'WRITE_ATTRIBUTES': 'write_attributes',
            'READ_EA': 'read_ea',
            'WRITE_EA': 'write_ea',
            'SYNCHRONIZE': 'synchronize',
            'READ_CONTROL': 'read_control',
            'WRITE_DAC': 'write_dac',
            'WRITE_OWNER': 'write_owner',
        }
        
        for key, value in special_map.items():
            if key in rights_str:
                rights.append(value)
        
        return rights if rights else ['special_access']
    
    def _is_inherited(self, flags: str) -> bool:
        if not flags:
            return False
        inherited_flags = ['I', 'IO', 'NP', 'OI', 'CI']
        return any(f in flags for f in inherited_flags)
    
    def _get_inherited_from(self, flags: str) -> Optional[str]:
        if self._is_inherited(flags):
            return "parent"
        return None
    
    def _get_principal_type(self, principal: str) -> str:
        if not principal:
            return 'unknown'
        principal_lower = principal.lower()
        
        if 'nt authority\\' in principal_lower:
            return 'system'
        if 'nt service\\' in principal_lower:
            return 'system'
        if 'local service' in principal_lower or 'network service' in principal_lower:
            return 'system'
        if 'builtin\\' in principal_lower:
            return 'group'
        if '\\' in principal:
            domain, name = principal.split('\\', 1)
            if domain.lower() not in ['builtin', 'nt authority', 'nt service']:
                return 'local_user'
            return 'group'
        if principal.startswith('S-1-'):
            return 'sid'
        return 'local_user'
    
    def _get_principal_sid(self, principal: str) -> Optional[str]:
        return None
    
    def _get_principal_domain(self, principal: str) -> Optional[str]:
        if '\\' in principal:
            return principal.split('\\')[0]
        return None
    
    def get_effective_permissions(self, resource_path: str, principal: str) -> List[str]:
        if not self.is_available() or not resource_path or not principal:
            return []
        try:
            result = subprocess.run(
                ['icacls', resource_path, principal],
                capture_output=True,
                text=True,
                encoding=self._encoding,
                errors='ignore',
                timeout=30
            )
            return self._parse_effective_output(result.stdout)
        except:
            return []
    
    def _parse_effective_output(self, output: str) -> List[str]:
        permissions = set()
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            matches = re.findall(r'\(([A-Z]+)\)', line)
            for match in matches:
                perms = self._parse_rights(match)
                permissions.update(perms)
            if '(special access' in line:
                special_match = re.search(r'special access:([^)]*)', line)
                if special_match:
                    perms = self._parse_special_rights(special_match.group(1))
                    permissions.update(perms)
        return list(permissions)
    
    def get_principals(self) -> List[Dict]:
        principals = []
        seen_names = set()
        if platform.system() != 'Windows':
            return principals
        
        try:
            result = subprocess.run(['net', 'user'], capture_output=True, text=True, encoding=self._encoding, timeout=30)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if any(line.startswith(x) for x in ['---', '====', 'Имя', 'User', '-------']):
                        continue
                    if 'Команда' in line or 'Command' in line:
                        break
                    parts = line.split()
                    for part in parts:
                        if part and len(part) > 1 and not part.startswith('-'):
                            if part not in ['*', '-----', '=======', '===']:
                                if re.match(r'^[a-zA-Zа-яА-Я0-9_\.\-]+$', part):
                                    key = f"local_user:{part}"
                                    if key not in seen_names:
                                        seen_names.add(key)
                                        principals.append({
                                            "name": part,
                                            "type": "local_user",
                                            "domain": "LOCAL",
                                            "sid": None
                                        })
        except:
            pass
        
        try:
            result = subprocess.run(['net', 'localgroup'], capture_output=True, text=True, encoding=self._encoding, timeout=30)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if any(line.startswith(x) for x in ['---', '====', 'Псевдоним', 'Alias', '-------']):
                        continue
                    if 'Команда' in line or 'Command' in line:
                        break
                    parts = line.split()
                    for part in parts:
                        if part and len(part) > 1 and not part.startswith('-'):
                            if part not in ['*', '-----', '=======', '===']:
                                if re.match(r'^[a-zA-Zа-яА-Я0-9_\.\-]+$', part):
                                    key = f"group:{part}"
                                    if key not in seen_names:
                                        seen_names.add(key)
                                        principals.append({
                                            "name": part,
                                            "type": "group",
                                            "domain": "LOCAL",
                                            "sid": None
                                        })
        except:
            pass
        
        builtin_groups = ['Administrators', 'Users', 'Guests', 'Backup Operators', 'Power Users']
        for group in builtin_groups:
            key = f"group:{group}"
            if key not in seen_names:
                seen_names.add(key)
                principals.append({
                    "name": group,
                    "type": "group",
                    "domain": "BUILTIN",
                    "sid": None
                })
        return principals
    
    def get_principal_groups(self, principal: str) -> List[str]:
        if not principal or platform.system() != 'Windows':
            return []
        groups = []
        try:
            result = subprocess.run(['net', 'user', principal], capture_output=True, text=True, encoding=self._encoding, timeout=30)
            if result.returncode != 0:
                return []
            in_groups = False
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if any(key in line for key in ['Глобальные группы', 'Local Group Memberships', 'Группы']):
                    in_groups = True
                    continue
                if in_groups:
                    if not line or line.startswith('Команда') or line.startswith('The'):
                        break
                    parts = line.split()
                    for part in parts:
                        if part and not part.startswith('*'):
                            if re.match(r'^[a-zA-Zа-яА-Я0-9_\.\-]+$', part):
                                groups.append(part)
                                break
                if in_groups and line.startswith('Команда'):
                    break
        except:
            pass
        return groups
    
    def get_source_type(self) -> str:
        return "local"
    
    def is_available(self) -> bool:
        return self._available