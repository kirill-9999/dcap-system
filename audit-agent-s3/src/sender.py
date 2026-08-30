# audit-agent-s3/src/sender.py
import time
import logging
from typing import Optional, List

import requests

from shared.event_schema import UnifiedEvent

logger = logging.getLogger(__name__)


class Sender:
    """Отправка событий в Manager (HTTP + JWT-поддержка)."""

    def __init__(self, config: dict):
        self.manager_url = config["manager"]["url"].rstrip("/")
        self.timeout = int(config["manager"].get("timeout", 30))
        self.max_retries = int(config["manager"].get("max_retries", 3))
        self.retry_delay = int(config["manager"].get("retry_delay", 5))
        self.agent_id = None

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "dcap-s3-agent/3.0.0",
        })

        self.token = None

        logger.info(f"Sender initialized: {self.manager_url}")

    def set_token(self, token: str):
        """Установка JWT токена."""
        self.token = token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    def register_agent(self, agent_data: dict) -> Optional[dict]:
        """Регистрация агента в Manager."""
        try:
            response = self.session.post(
                f"{self.manager_url}/api/audit/agents/register",
                json=agent_data,
                timeout=self.timeout,
            )
            if response.status_code in [200, 201]:
                data = response.json()
                self.agent_id = data.get("agent_id")
                logger.info(f"Agent registered: {agent_data['name']} (id={self.agent_id})")
                return data
            else:
                logger.error(
                    f"Registration failed: {response.status_code}, {response.text[:200]}"
                )
                return None
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return None

    def send_events_batch(self, events: List[UnifiedEvent]) -> bool:
        """Пакетная отправка событий в Manager (/api/audit/events)."""
        if not events:
            return True
        data = [e.model_dump() for e in events]
        return self._post("/api/audit/events", {"agent_id": self.agent_id, "events": data})

    def send_heartbeat(self, status: str = "online", stats: Optional[dict] = None) -> bool:
        """Отправка heartbeat в Manager."""
        payload = {
            "agent_id": self.agent_id,
            "status": status,
            "stats": stats if stats is not None else self._get_stats(),
        }
        try:
            response = self.session.post(
                f"{self.manager_url}/api/audit/agents/heartbeat",
                json=payload,
                timeout=10,
            )
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            return False

    def _post(self, endpoint: str, data: dict) -> bool:
        """Выполнение POST с экспоненциальной задержкой при retry."""
        return self._send_request(endpoint, data)

    def _send_request(self, endpoint: str, data: dict) -> bool:
        """Выполнение запроса с экспоненциальной задержкой.

        Обрабатывает:
        - 200/201/202 — успех
        - 429 — rate limiting (учитывает Retry-After)
        - 500/502/503/504 — server errors (retry)
        - 401 — ошибка аутентификации (без retry)
        - таймауты и сетевые ошибки (retry)
        """
        url = f"{self.manager_url}{endpoint}"
        retries = 0
        delay = self.retry_delay
        max_backoff = 60

        while retries < self.max_retries:
            try:
                response = self.session.post(url, json=data, timeout=self.timeout)

                if response.status_code in [200, 201, 202]:
                    logger.debug(f"Request successful: {endpoint}")
                    return True
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", delay)
                    try:
                        retry_after = int(retry_after)
                    except (TypeError, ValueError):
                        retry_after = delay
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    retries += 1
                    delay = min(delay * 2, max_backoff)
                elif response.status_code in [500, 502, 503, 504]:
                    logger.warning(
                        f"Server error {response.status_code}, retrying "
                        f"({retries + 1}/{self.max_retries})..."
                    )
                    time.sleep(delay)
                    retries += 1
                    delay = min(delay * 2, max_backoff)
                elif response.status_code == 401:
                    logger.error("Authentication failed, token may be expired")
                    return False
                else:
                    logger.error(
                        f"Request failed: {response.status_code}, {response.text[:200]}"
                    )
                    return False

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Timeout, retrying... ({retries + 1}/{self.max_retries})"
                )
                time.sleep(delay)
                retries += 1
                delay = min(delay * 2, max_backoff)

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Request error: {e}, retrying... ({retries + 1}/{self.max_retries})"
                )
                time.sleep(delay)
                retries += 1
                delay = min(delay * 2, max_backoff)

        return False

    def _get_stats(self) -> dict:
        """Статистика для heartbeat."""
        return {
            "version": "3.0.0",
            "source_type": "s3",
        }
