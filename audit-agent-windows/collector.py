"""Чтение Security Log через wevtutil (Windows). XML — локонезависимый формат."""

import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict


class WindowsAuditCollector:
    def __init__(self):
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            subprocess.run(['wevtutil', '--help'], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def collect_events(self, since: datetime, event_ids: List[int], limit: int = 1000) -> List[Dict]:
        if not self._available:
            return []

        # wevtutil не поддерживает TimeCreated в XPath — фильтруем по EventID,
        # время отсеиваем в Python после парсинга.
        # /e Events не используется — wevtutil отдаёт голые <Event>.
        or_clause = " or ".join(f"EventID={eid}" for eid in event_ids)
        query = f"*[System[({or_clause})]]"

        try:
            result = subprocess.run(
                ['wevtutil', 'qe', 'Security',
                 '/q:' + query,
                 '/f:XML',
                 '/c:' + str(limit)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            all_events = self._parse_xml(result.stdout, event_ids)

            # Фильтр по времени в Python
            return [e for e in all_events
                    if e.get('created_at') and e['created_at'] >= since.strftime("%Y-%m-%dT%H:%M:%S")]
        except Exception as e:
            print(f"[Collector] Ошибка: {e}")
            return []

    def _parse_xml(self, output: str, event_ids: List[int]) -> List[Dict]:
        events = []
        output = output.strip()
        if not output:
            return []

        # Убираем namespace — wevtutil отдаёт xmlns=... ломает findall
        output = output.replace("xmlns='http://schemas.microsoft.com/win/2004/08/events/event'", "")

        # wevtutil без /e Events отдаёт голые <Event> без корневого элемента — оборачиваем
        if not output.startswith('<Events>'):
            output = f"<Events>{output}</Events>"

        root = ET.fromstring(output)
        for elem in root.findall('Event'):
            sys_el = elem.find('System')
            if sys_el is None:
                continue

            eid_el = sys_el.find('EventID')
            if eid_el is None:
                continue
            try:
                eid = int(eid_el.text)
            except (ValueError, TypeError):
                continue

            if eid not in event_ids:
                continue

            tc_el = sys_el.find('TimeCreated')
            timestamp = tc_el.get('SystemTime', '') if tc_el is not None else ''

            data = {}
            for d in elem.findall('.//EventData/Data'):
                name = d.get('Name', '')
                val = d.text or ''
                data[name] = val

            events.append(self._normalize_event(eid, timestamp, data))

        return events

    def _normalize_event(self, eid: int, timestamp: str, data: Dict) -> Dict:
        event_type_map = {
            4656: 'read',
            4660: 'delete',
            4663: 'write',
            4670: 'write',
            5140: 'read',
            5145: 'read',
        }

        # 4663:ObjectName, 4656:ObjectName, 5140/5145:ShareName/RelativeTargetName
        file_path = (
            data.get('ObjectName')
            or data.get('ShareName', '')
            + data.get('RelativeTargetName', '')
            or ''
        )

        old_path = data.get('OldFileName') or data.get('OldPath')
        new_path = data.get('NewFileName') or data.get('NewPath')

        created_at = timestamp
        if timestamp and 'T' in timestamp:
            created_at = timestamp.split('.')[0] + 'Z'

        import socket
        hostname = socket.gethostname()

        return {
            'event_type': event_type_map.get(eid, 'unknown'),
            'event_source': 'windows_agent',
            'user': data.get('SubjectUserName'),
            'user_sid': data.get('SubjectUserSid'),
            'file_path': file_path,
            'old_path': old_path,
            'new_path': new_path,
            'source_host': hostname,
            'metadata': {
                'event_id': eid,
                'subject_domain': data.get('SubjectDomainName'),
                'process_name': data.get('ProcessName'),
                'access_mask': data.get('AccessMask'),
                'access_list': data.get('AccessList'),
            },
            'created_at': created_at,
        }
