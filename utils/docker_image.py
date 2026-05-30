"""Docker 镜像引用解析与拉取相关工具。"""
from typing import Any, Dict, Optional, Tuple

from core.exceptions import ImageBuildError


def extract_docker_error_message(exc: Exception) -> str:
    """提取 Docker SDK 异常中的可读错误信息。"""
    explanation = getattr(exc, "explanation", None)
    if isinstance(explanation, bytes):
        try:
            explanation = explanation.decode("utf-8", errors="ignore")
        except Exception:
            explanation = None

    message = str(explanation or exc or "").strip()
    return message or "Docker 操作失败"


def split_image_reference(image_ref: str) -> Tuple[str, Optional[str]]:
    """拆分镜像引用为 repository 与 tag/digest。"""
    text = str(image_ref or "").strip()
    if not text:
        return "", None

    if "@" in text:
        repository, digest = text.rsplit("@", 1)
        return repository, digest or None

    last_slash = text.rfind("/")
    last_colon = text.rfind(":")
    if last_colon > last_slash:
        return text[:last_colon], text[last_colon + 1:] or None

    return text, None


def format_pull_progress_event(chunk: Dict[str, Any]) -> Optional[str]:
    status = str(chunk.get("status") or "").strip()
    identifier = str(chunk.get("id") or "").strip()
    progress = str(chunk.get("progress") or "").strip()
    if not status:
        return None

    parts = [status]
    if identifier:
        parts.append(identifier)
    line = " | ".join(parts)
    if progress:
        line = f"{line} {progress}"
    return line


def is_pull_not_found_message(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    if "access denied" in text or "denied:" in text:
        return False
    return "manifest unknown" in text or "not found" in text or "failed to resolve reference" in text


def build_pull_not_found_hint(requested_image: str, resolved_image: str) -> str:
    requested = str(requested_image or "").strip()
    candidate = requested or str(resolved_image or "").strip()
    return f"请确认镜像名 {candidate or resolved_image} 是否正确，或当前镜像源是否提供该镜像。"


def format_pull_error_message(message: str, requested_image: str, resolved_image: str) -> Tuple[bool, str]:
    normalized = str(message or "").strip() or "未知错误"
    if is_pull_not_found_message(normalized):
        hint = build_pull_not_found_hint(requested_image, resolved_image)
        return True, f"未找到可拉取镜像: {resolved_image}。{hint}"
    return False, f"拉取镜像失败: {normalized}"


def resolve_image_reference(image: str, image_source: Optional[str] = None) -> str:
    """根据可选镜像源拼接或改写镜像引用。"""
    image_ref = str(image or "").strip()
    if not image_ref:
        raise ImageBuildError("镜像名不能为空")

    source = str(image_source or "").strip()
    if not source:
        return image_ref

    source = source.rstrip("/")
    if source.startswith("http://"):
        source = source[len("http://"):]
    elif source.startswith("https://"):
        source = source[len("https://"):]

    if not source:
        raise ImageBuildError("镜像源不能为空")

    # 判断镜像是否已包含 registry 前缀
    # 只看 "/" 前的部分；需排除 tag 中的 ":" 干扰（如 nginx:latest）
    parts = image_ref.split("/", 1)
    first_segment = parts[0].split(":")[0]
    has_registry = ("." in first_segment or first_segment == "localhost") and len(parts) > 1

    if not has_registry:
        return f"{source}/{image_ref}"

    if image_ref.startswith(f"{source}/"):
        return image_ref

    _, remainder = image_ref.split("/", 1)
    return f"{source}/{remainder}"
