"""
Сбор событий файловой системы Windows через wevtutil.
Работает на Windows 10 Home/Pro/Server.
"""

import subprocess
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class WindowsAuditCollector:
    """Чтение Security Log через wevtutil"""

    def __init__(self):
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            subprocess.run(['wevtutil', '--help'], capture_output=True, timeout=5)
            return True
        except:
            return False

    def collect_events(self, since: Optional[datetime] = None,
                       event_ids: Optional[List[int]] = None,
                       limit: int = 1000) -> List[Dict]:
        """
        Собрать события из Security Log

        Аргументы:
            since: собирать события с указанного времени
            event_ids: список Event ID для фильтрации
            limit: максимум событий

        Возвращает:
            List[Dict]: список событий
        """
        if not self._available:
            return []

        if since is None:
            since = datetime.utcnow() - timedelta(hours=24)

        if event_ids is None:
            event_ids = [4656, 4660, 4663, 4670, 5140, 5145]

        time_filter = since.strftime("%Y-%m-%dT%H:%M:%S")
        query = f"*[System[TimeCreated[@SystemTime>='{time_filter}']]]"

        try:
            result = subprocess.run(
                ['wevtutil', 'qe', 'Security',
                 '/q', query,
                 '/e', 'Events',
                 '/f', 'Text',
                 '/c', str(limit)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            return self._parse_events(result.stdout, event_ids)
        except Exception as e:
            print(f"[Audit] Ошибка сбора событий: {e}")
            return []

    def _parse_events(self, output: str, event_ids: List[int]) -> List[Dict]:
        """Парсинг вывода wevtutil"""
        events = []
        current = {}
        in_event = False

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('Event['):
                if current and in_event:
                    events.append(current)
                    current = {}
                in_event = True
                continue

            if not in_event:
                continue

            if line.startswith('EventId:'):
                try:
                    eid = int(line.split(':', 1)[1].strip())
                    if eid not in event_ids:
                        in_event = False
                        current = {}
                        continue
                    current['event_id'] = eid
                except:
                    pass

            elif line.startswith('TimeCreated:'):
                current['timestamp'] = line.split(':', 1)[1].strip()

            elif 'SubjectUserName:' in line:
                current['user'] = line.split(':', 1)[1].strip()

            elif 'ObjectName:' in line:
                current['file_path'] = line.split(':', 1)[1].strip()

            elif 'AccessMask:' in line:
                current['access_mask'] = line.split(':', 1)[1].strip()

            elif 'OldPath:' in line:
                current['old_path'] = line.split(':', 1)[1].strip()

            elif 'NewPath:' in line:
                current['new_path'] = line.split(':', 1)[1].strip()

        if current and in_event:
            events.append(current)

        return events

    def map_event_to_audit(self, raw: Dict) -> Dict:
        """Преобразовать raw-событие в формат AuditLog"""
        event_id = raw.get('event_id')
        event_type = self._map_event_type(event_id)

        return {
            'event_type': event_type,
            'user': raw.get('user'),
            'file_path': raw.get('file_path', ''),
            'old_path': raw.get('old_path'),
            'metadata': {
                'event_id': event_id,
                'access_mask': raw.get('access_mask')
            },
            'created_at': self._parse_timestamp(raw.get('timestamp'))
        }

    def _map_event_type(self, event_id: int) -> str:
        mapping = {
            4656: 'read',
            4660: 'delete',
            4663: 'write',
            4670: 'write',
            5140: 'read',
            5145: 'read',
        }
        return mapping.get(event_id, 'unknown')

    def _parse_timestamp(self, ts: str) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except:
            return None
