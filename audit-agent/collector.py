"""Чтение Security Log через wevtutil (Windows)."""

import subprocess
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class WindowsAuditCollector:
    def __init__(self):
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            subprocess.run(['wevtutil', '--help'], capture_output=True, timeout=5)
            return True
        except:
            return False

    def collect_events(self, since: datetime, event_ids: List[int], limit: int = 1000) -> List[Dict]:
        if not self._available:
            return []

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
            print(f"[Collector] Ошибка: {e}")
            return []

    def _parse_events(self, output: str, event_ids: List[int]) -> List[Dict]:
        events = []
        current = {}
        in_event = False

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('Event['):
                if current and in_event:
                    events.append(self._normalize_event(current))
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

            elif 'OldPath:' in line:
                current['old_path'] = line.split(':', 1)[1].strip()

            elif 'NewPath:' in line:
                current['new_path'] = line.split(':', 1)[1].strip()

        if current and in_event:
            events.append(self._normalize_event(current))

        return events

    def _normalize_event(self, raw: Dict) -> Dict:
        event_id = raw.get('event_id')
        event_type_map = {
            4656: 'read',
            4660: 'delete',
            4663: 'write',
            4670: 'write',
            5140: 'read',
            5145: 'read',
        }
        return {
            'event_type': event_type_map.get(event_id, 'unknown'),
            'user': raw.get('user'),
            'file_path': raw.get('file_path', ''),
            'old_path': raw.get('old_path'),
            'metadata': {
                'event_id': event_id,
                'raw': raw
            },
            'created_at': raw.get('timestamp')
        }
