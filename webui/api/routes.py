# webui/api/routes.py
"""
WebUI API — пассивный прокси к Manager (День 29.5, Вариант А).

Все /api/* запросы транслируются в Manager (:8000). Это устраняет дублирование
БД и API между WebUI и Manager: WebUI больше не читает БД напрямую.

HTTP-ошибки, ответы и бинарные стримы (отчёты PDF/XLSX) пробрасываются как есть.
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
import httpx
import logging

from webui.config import MANAGER_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["webui-proxy"])

MANAGER_TIMEOUT = 60.0

# Пути, которые НЕ являются API (страницы/статика обрабатываются в webui/main.py
# и в корневых роутах — здесь только /api/*)
PROXY = True


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_manager(request: Request, path: str):
    """Прокси всех /api/* запросов в Manager."""
    url = f"{MANAGER_URL}/api/{path}"

    params = dict(request.query_params)

    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        raw = await request.body()
        if raw:
            try:
                body = raw
            except Exception:
                body = None

    headers = {
        "Accept": "application/json, */*",
    }
    content_type = request.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type

    # Проброс аутентификации в Manager: заголовок Authorization (Bearer JWT)
    # и HttpOnly cookie access_token/refresh_token (SPNEGO/Basic fallback).
    auth_header = request.headers.get("authorization")
    if auth_header:
        headers["Authorization"] = auth_header

    cookies = dict(request.cookies)
    cookies.setdefault("access_token", "")
    cookies.setdefault("refresh_token", "")

    async with httpx.AsyncClient(timeout=MANAGER_TIMEOUT) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                params=params,
                content=body,
                headers=headers,
                cookies=cookies,
            )
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Manager: {MANAGER_URL}")
            return Response(
                content='{"detail":"Manager service unavailable"}',
                status_code=503,
                media_type="application/json",
            )
        except httpx.TimeoutException:
            logger.error(f"Manager timeout: {url}")
            return Response(
                content='{"detail":"Manager timeout"}',
                status_code=504,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"Proxy error: {e}")
            return Response(
                content='{"detail":"Proxy error"}',
                status_code=500,
                media_type="application/json",
            )

    content_type_resp = resp.headers.get("content-type", "")
    disposition = resp.headers.get("content-disposition")

    if disposition and "attachment" in disposition:
        # Бинарный стрим (PDF/XLSX) — пробрасываем как есть
        return StreamingResponse(
            resp.aiter_bytes(),
            status_code=resp.status_code,
            media_type=content_type_resp or "application/octet-stream",
            headers={"content-disposition": disposition},
        )

    content = resp.content

    # Пробрасываем тело и код ответа как есть
    return Response(
        content=content,
        status_code=resp.status_code,
        media_type=content_type_resp or "application/json",
    )
