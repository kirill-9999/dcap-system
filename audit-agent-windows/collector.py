"""Чтение Security Log через wevtutil (Windows). XML — локонезависимый формат."""

import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict


class WindowsAuditCollector:
    def __init__(self):
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            subprocess.run(["wevtutil", "--help"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def collect_events(
        self, since: datetime, event_ids: List[int], limit: int = 1000
    ) -> List[Dict]:
        if not self._available:
            return []

        # wevtutil не поддерживает TimeCreated в XPath — фильтруем по EventID,
        # время отсеиваем в Python после парсинга.
        # /e Events не используется — wevtutil отдаёт голые <Event>.
        or_clause = " or ".join(f"EventID={eid}" for eid in event_ids)
        query = f"*[System[({or_clause})]]"

        try:
            result = subprocess.run(
                ["wevtutil", "qe", "Security", "/q:" + query, "/f:XML", "/c:" + str(limit)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
            )
            all_events = self._parse_xml(result.stdout, event_ids)

            # Фильтр по времени в Python
            return [
                e
                for e in all_events
                if e.get("created_at") and e["created_at"] >= since.strftime("%Y-%m-%dT%H:%M:%S")
            ]
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
        if not output.startswith("<Events>"):
            output = f"<Events>{output}</Events>"

        root = ET.fromstring(output)
        for elem in root.findall("Event"):
            sys_el = elem.find("System")
            if sys_el is None:
                continue

            eid_el = sys_el.find("EventID")
            if eid_el is None:
                continue
            try:
                eid = int(eid_el.text)
            except (ValueError, TypeError):
                continue

            if eid not in event_ids:
                continue

            tc_el = sys_el.find("TimeCreated")
            timestamp = tc_el.get("SystemTime", "") if tc_el is not None else ""

            data = {}
            for d in elem.findall(".//EventData/Data"):
                name = d.get("Name", "")
                val = d.text or ""
                data[name] = val

            events.append(self._normalize_event(eid, timestamp, data))

        return events

    def _normalize_event(self, eid: int, timestamp: str, data: Dict) -> Dict:
        event_type_map = {
            4656: "read",
            4660: "delete",
            4663: "write",
            4670: "write",
            5140: "read",
            5145: "read",
        }

        # 4663:ObjectName, 4656:ObjectName, 5140/5145:ShareName/RelativeTargetName
        file_path = (
            data.get("ObjectName")
            or data.get("ShareName", "") + data.get("RelativeTargetName", "")
            or ""
        )

        old_path = data.get("OldFileName") or data.get("OldPath")
        new_path = data.get("NewFileName") or data.get("NewPath")

        created_at = timestamp
        if timestamp and "T" in timestamp:
            created_at = timestamp.split(".")[0] + "Z"

        import socket

        hostname = socket.gethostname()

        return {
            "event_type": event_type_map.get(eid, "unknown"),
            "event_source": "windows_agent",
            "user": data.get("SubjectUserName"),
            "user_sid": data.get("SubjectUserSid"),
            "file_path": file_path,
            "old_path": old_path,
            "new_path": new_path,
            "source_host": hostname,
            "metadata": {
                "event_id": eid,
                "subject_domain": data.get("SubjectDomainName"),
                "process_name": data.get("ProcessName"),
                "access_mask": data.get("AccessMask"),
                "access_list": data.get("AccessList"),
            },
            "created_at": created_at,
        }

    # ------------------------------------------------------------------
    # Сбор NTFS прав (День 33)
    # ------------------------------------------------------------------
    def collect_permissions(self, path: str) -> List[Dict]:
        """Сбор NTFS/ACL прав для пути через win32security (fallback — icacls)."""
        if not os.path.exists(path):
            return []

        entries = self._collect_win32(path)
        if entries is None:
            entries = self._collect_icacls(path)
        return entries

    def _collect_win32(self, path: str):
        """Сбор прав через win32security. Возвращает None, если недоступен."""
        try:
            import win32security
            import win32file
        except ImportError:
            return None

        try:
            sd = win32security.GetFileSecurity(path, win32security.DACL_SECURITY_INFORMATION)
            dacl = sd.GetSecurityDescriptorDacl()
        except Exception:
            return []

        entries = []
        import pywintypes

        def map_mask(mask):
            perms = []
            if mask & win32security.FILE_GENERIC_READ:
                perms.append("read")
            if mask & win32security.FILE_GENERIC_WRITE:
                perms.append("write")
            if mask & win32security.FILE_DELETE_CHILD:
                perms.append("delete")
            if mask & win32security.FILE_EXECUTE:
                perms.append("execute")
            if mask & win32security.FILE_ALL_ACCESS:
                perms.append("full_control")
            return perms

        domain = None
        for i in range(dacl.GetAceCount()):
            try:
                ace = dacl.GetAce(i)
                ace_type, ace_flags, mask, sid = ace
                account, _domain, _type = win32security.LookupAccountSid(None, sid)
                domain = domain or _domain
                principal_type = "group" if _type == win32security.SidTypeGroup else "user"
                inherited = bool(
                    ace_flags & win32security.OBJECT_INHERIT_ACE
                    or ace_flags & win32security.CONTAINER_INHERIT_ACE
                )
                perms = map_mask(mask)
                if not perms:
                    continue
                entries.append(
                    {
                        "resource_path": path,
                        "principal_type": principal_type,
                        "principal_name": f"{_domain}\\{account}" if _domain else account,
                        "principal_sid": str(sid),
                        "principal_domain": _domain,
                        "permissions": perms,
                        "permission_source": "inherited" if inherited else "direct",
                        "is_inherited": inherited,
                    }
                )
            except Exception:
                continue
        return entries

    def _collect_icacls(self, path: str) -> List[Dict]:
        """Fallback-сбор прав через icacls (текстовый парсинг) — не требует pywin32."""
        try:
            result = subprocess.run(
                ["icacls", path],
                capture_output=True,
                text=True,
                encoding="cp866",
                errors="replace",
                timeout=30,
            )
        except Exception:
            return []
        entries = []
        for line in (result.stdout or "").splitlines():
            line = line.rstrip()
            line = line.strip()
            if not line or line.lower().startswith("успешно") or line.lower().startswith("processed") or line.endswith(":"):
                continue
            if "(" not in line:
                continue
            idx = line.find("(")
            principal = line[:idx].strip()
            rights = line[idx:].strip()
            if principal.lower().startswith(path.lower()):
                principal = principal[len(path):].strip()
            principal = principal.rstrip(":").strip()
            if not principal or not rights:
                continue
            perms = []
            uper = rights.upper()
            if "F" in uper:
                perms.append("full_control")
            if "M" in uper or "W" in uper:
                perms.append("write")
            if "R" in uper or "RX" in uper:
                perms.append("read")
            if "D" in uper:
                perms.append("delete")
            if not perms:
                perms.append("read")
            entries.append(
                {
                    "resource_path": path,
                    "principal_type": "group" if principal.startswith("*") else "user",
                    "principal_name": principal,
                    "permissions": perms,
                    "permission_source": "direct",
                    "is_inherited": False,
                }
            )
        return entries
