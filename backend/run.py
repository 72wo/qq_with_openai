"""按配置文件启动 FastAPI 服务。"""

import os
import sys
import uvicorn

try:
    from .config import Config
except ImportError:
    current_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from backend.config import Config


def main():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default_config.json")
    runtime_config = Config(config_path)

    config_port = runtime_config.get("advanced.service_port", 5000)
    port = int(os.getenv("FLASK_PORT", config_port))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    reload_enabled = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    uvicorn.run("backend.app:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    main()
