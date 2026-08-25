"""Запуск WebUI DCAP (webui.main:app) на отдельном порту :8001."""
import uvicorn

from webui.config import WEBUI_HOST, WEBUI_PORT, DEBUG

if __name__ == "__main__":
    uvicorn.run(
        "webui.main:app",
        host=WEBUI_HOST,
        port=WEBUI_PORT,
        reload=DEBUG,
        log_level="info"
    )
