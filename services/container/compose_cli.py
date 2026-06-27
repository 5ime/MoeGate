"""Docker Compose CLI 封装。"""
import logging
import os
import subprocess
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def _build_compose_cmd(
    compose_files: Sequence[str],
    project_name: str,
    args: Sequence[str],
) -> List[str]:
    cmd = ["docker", "compose"]
    for compose_file in compose_files:
        cmd.extend(["-f", compose_file])
    cmd.extend(["-p", project_name])
    cmd.extend(args)
    return cmd


def run_compose_command(
    compose_files: Sequence[str],
    project_name: str,
    args: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    cmd = _build_compose_cmd(compose_files, project_name, args)
    logger.debug("执行 compose 命令: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=cwd or os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def compose_up(
    compose_files: Sequence[str],
    project_name: str,
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    return run_compose_command(
        compose_files,
        project_name,
        ["up", "-d", "--remove-orphans"],
        cwd=cwd,
        env=env,
        timeout=timeout,
    )


def compose_down(
    compose_files: Sequence[str],
    project_name: str,
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    return run_compose_command(
        compose_files,
        project_name,
        ["down", "--remove-orphans"],
        cwd=cwd,
        env=env,
        timeout=timeout,
    )


def extract_compose_failure(output: str) -> str:
    """从 compose 输出中提取最有用的错误行。"""
    lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
    if not lines:
        return "compose command failed"

    error_lines = [
        line
        for line in lines
        if any(token in line.lower() for token in ("error", "failed", "denied", "invalid"))
    ]
    if error_lines:
        return error_lines[-1]
    return lines[-1]
