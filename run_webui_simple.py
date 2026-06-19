import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from webui.main_simple import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run("webui.main_simple:app", host="0.0.0.0", port=8001, reload=True)