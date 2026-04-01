from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
WEB_LOG = ROOT / "web-dev.log"
BACKEND_LOG = ROOT / "backend-dev.log"
DETACHED_FLAGS = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
COREPACK_CMD = Path(r"D:\nodejs\corepack.cmd")


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start_web() -> None:
    if is_port_open(3000):
        print("web: already listening on 3000")
        return

    command = (
        [str(COREPACK_CMD), "pnpm", "dev:web"]
        if COREPACK_CMD.exists()
        else ["cmd.exe", "/c", "corepack pnpm dev:web"]
    )

    with WEB_LOG.open("ab") as log_file:
        subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            creationflags=DETACHED_FLAGS,
        )
    print(f"web: starting, log -> {WEB_LOG}")


def start_backend() -> None:
    if is_port_open(8000):
        print("backend: already listening on 8000")
        return

    python_exe = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    command = (
        [str(python_exe), "-m", "uvicorn", "main:app", "--reload", "--port", "8000"]
        if python_exe.exists()
        else ["python", "-m", "uvicorn", "main:app", "--reload", "--port", "8000"]
    )

    with BACKEND_LOG.open("ab") as log_file:
        subprocess.Popen(
            command,
            cwd=str(BACKEND_DIR),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            creationflags=DETACHED_FLAGS,
        )
    print(f"backend: starting, log -> {BACKEND_LOG}")


def main() -> int:
    start_backend()
    start_web()
    time.sleep(3)
    print(f"backend_port_8000={is_port_open(8000)}")
    print(f"web_port_3000={is_port_open(3000)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
