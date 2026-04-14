"""Docker 镜像管理服务。"""
from typing import Any, Dict, List, Optional, Tuple

import docker

from config import AppConfig, config as default_config
from core.exceptions import ContainerServiceError, DockerConnectionError, ValidationError
from infra.docker import ensure_client
from services.container.builder import _resolve_image_reference
from utils.image_registry import (
    list_managed_image_records,
    register_managed_image,
    resolve_registered_image_ref,
    unregister_managed_image,
    upsert_managed_image_tags,
)


def _docker_error_message(exc: Exception) -> str:
    explanation = getattr(exc, "explanation", None)
    if isinstance(explanation, bytes):
        try:
            explanation = explanation.decode("utf-8", errors="ignore")
        except Exception:
            explanation = None
    text = str(explanation or exc or "").strip()
    return text or "Docker 操作失败"


def _is_pull_not_found_message(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    if "access denied" in text or "denied:" in text:
        return False
    return "manifest unknown" in text or "not found" in text or "failed to resolve reference" in text


def _raise_pull_error(message: str, requested_image: str, resolved_image: str, default_code: int = 500):
    normalized = str(message or "").strip() or "未知错误"
    if _is_pull_not_found_message(normalized):
        hint = f"请确认镜像名 {requested_image or resolved_image} 是否正确，或当前镜像源是否提供该镜像。"
        raise ContainerServiceError(f"未找到可拉取镜像: {resolved_image}。{hint}", 404)
    raise ContainerServiceError(f"拉取镜像失败: {normalized}", default_code)


def _format_bytes(size_bytes: int) -> str:
    value = float(max(int(size_bytes or 0), 0))
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return "0 B"


def _normalize_tags(tags: Optional[List[str]]) -> List[str]:
    normalized = []
    for tag in tags or []:
        text = str(tag or "").strip()
        if not text or text == "<none>:<none>":
            continue
        normalized.append(text)
    return normalized


def _split_image_reference(image_ref: str) -> Tuple[str, Optional[str]]:
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


def _format_pull_progress_event(chunk: Dict[str, Any]) -> Optional[str]:
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


def _normalize_container_name(container) -> str:
    name = str(getattr(container, "name", "") or "").strip()
    if name:
        return name
    attrs = getattr(container, "attrs", None) or {}
    raw = str(attrs.get("Name") or "").strip()
    return raw.lstrip("/")


def _collect_image_usage(client) -> Tuple[Dict[str, int], Dict[str, List[Dict[str, Any]]]]:
    usage_count: Dict[str, int] = {}
    usage_refs: Dict[str, List[Dict[str, Any]]] = {}

    try:
        containers = client.containers.list(all=True)
    except Exception:
        return usage_count, usage_refs

    for container in containers:
        attrs = getattr(container, "attrs", None) or {}
        image_id = str(attrs.get("Image") or getattr(getattr(container, "image", None), "id", "") or "").strip()
        if not image_id:
            continue

        usage_count[image_id] = usage_count.get(image_id, 0) + 1
        usage_refs.setdefault(image_id, []).append(
            {
                "id": str(getattr(container, "id", "") or ""),
                "name": _normalize_container_name(container),
                "status": str((attrs.get("State") or {}).get("Status") or getattr(container, "status", "") or ""),
            }
        )

    return usage_count, usage_refs


def _collect_managed_image_usage(client) -> Tuple[Dict[str, int], Dict[str, List[Dict[str, Any]]]]:
    usage_count: Dict[str, int] = {}
    usage_refs: Dict[str, List[Dict[str, Any]]] = {}

    try:
        containers = client.containers.list(all=True, filters={"label": "moegate.managed=true"})
    except Exception:
        return usage_count, usage_refs

    for container in containers:
        attrs = getattr(container, "attrs", None) or {}
        image_id = str(attrs.get("Image") or getattr(getattr(container, "image", None), "id", "") or "").strip()
        if not image_id:
            continue

        usage_count[image_id] = usage_count.get(image_id, 0) + 1
        usage_refs.setdefault(image_id, []).append(
            {
                "id": str(getattr(container, "id", "") or ""),
                "name": _normalize_container_name(container),
                "status": str((attrs.get("State") or {}).get("Status") or getattr(container, "status", "") or ""),
                "managed": True,
            }
        )

    return usage_count, usage_refs


def _serialize_image(
    image,
    usage_count: int = 0,
    usage_refs: Optional[List[Dict[str, Any]]] = None,
    registry_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attrs = getattr(image, "attrs", None) or {}
    tags = _normalize_tags(attrs.get("RepoTags"))
    repo_digests = [str(item) for item in (attrs.get("RepoDigests") or []) if str(item or "").strip()]
    size_bytes = int(attrs.get("Size") or attrs.get("VirtualSize") or 0)
    created_at = str(attrs.get("Created") or "")
    labels = ((attrs.get("Config") or {}).get("Labels") or {}) if isinstance(attrs.get("Config"), dict) else {}
    image_id = str(getattr(image, "id", "") or "")
    short_id = image_id
    if image_id.startswith("sha256:") and len(image_id) > 19:
        short_id = image_id[:19]

    registry_record = registry_record or {}
    managed_reasons = []
    if registry_record:
        managed_reasons.append("registry")
    if int(usage_count or 0) > 0:
        managed_reasons.append("container")

    return {
        "id": image_id,
        "short_id": short_id,
        "tags": tags,
        "primary_tag": tags[0] if tags else "<dangling>",
        "repo_digests": repo_digests,
        "created_at": created_at,
        "size_bytes": size_bytes,
        "size_text": _format_bytes(size_bytes),
        "containers_using": int(usage_count or 0),
        "container_refs": usage_refs or [],
        "is_dangling": len(tags) == 0,
        "managed": True,
        "managed_source": str(registry_record.get("source") or ("managed-container" if usage_count else "registry")).strip() or "registry",
        "managed_requested_image": str(registry_record.get("requested_image") or "").strip(),
        "managed_resolved_image": str(registry_record.get("resolved_image") or "").strip(),
        "managed_created_at": str(registry_record.get("created_at") or created_at or "").strip(),
        "managed_updated_at": str(registry_record.get("updated_at") or created_at or "").strip(),
        "managed_reasons": managed_reasons,
        "labels": labels,
        "architecture": str(attrs.get("Architecture") or ""),
        "os": str(attrs.get("Os") or ""),
        "author": str(attrs.get("Author") or ""),
    }


def _ensure_client():
    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")
    return client


def list_images() -> Dict[str, Any]:
    client = _ensure_client()
    try:
        registry_records = list_managed_image_records()
        usage_count, usage_refs = _collect_managed_image_usage(client)
        managed_image_ids = set(registry_records.keys()) | set(usage_count.keys())

        items = []
        missing_registry_ids = []
        for image_id in managed_image_ids:
            try:
                image = client.images.get(image_id)
            except docker.errors.ImageNotFound:
                if image_id in registry_records and usage_count.get(image_id, 0) <= 0:
                    missing_registry_ids.append(image_id)
                continue

            image_tags = _normalize_tags((getattr(image, "attrs", None) or {}).get("RepoTags"))
            if image_id in registry_records:
                upsert_managed_image_tags(image_id, image_tags)

            items.append(
                _serialize_image(
                    image,
                    usage_count=usage_count.get(image.id, 0),
                    usage_refs=usage_refs.get(image.id, []),
                    registry_record=registry_records.get(image.id),
                )
            )

        for image_id in missing_registry_ids:
            unregister_managed_image(image_id)

        items.sort(key=lambda item: (item["containers_using"], item["created_at"], item["size_bytes"]), reverse=True)

        total_size_bytes = sum(int(item.get("size_bytes") or 0) for item in items)
        dangling = sum(1 for item in items if item.get("is_dangling"))
        in_use = sum(1 for item in items if int(item.get("containers_using") or 0) > 0)

        return {
            "images": items,
            "total": len(items),
            "dangling": dangling,
            "in_use": in_use,
            "unused": len(items) - in_use,
            "total_size_bytes": total_size_bytes,
            "total_size_text": _format_bytes(total_size_bytes),
            "scope": "managed",
        }
    except docker.errors.APIError as exc:
        raise ContainerServiceError(f"获取受管镜像列表失败: {_docker_error_message(exc)}", 500)


def get_image_detail(image_ref: str) -> Dict[str, Any]:
    ref = str(image_ref or "").strip()
    if not ref:
        raise ValidationError("镜像标识不能为空")

    client = _ensure_client()
    try:
        image = client.images.get(ref)
        usage_count, usage_refs = _collect_managed_image_usage(client)
        registry_records = list_managed_image_records()
        if image.id not in registry_records and usage_count.get(image.id, 0) <= 0:
            raise ContainerServiceError(f"未找到指定受管镜像: {ref}", 404)
        detail = _serialize_image(
            image,
            usage_count=usage_count.get(image.id, 0),
            usage_refs=usage_refs.get(image.id, []),
            registry_record=registry_records.get(image.id),
        )
        detail["attrs"] = getattr(image, "attrs", None) or {}
        return detail
    except docker.errors.ImageNotFound:
        resolved_id = resolve_registered_image_ref(ref)
        if resolved_id and resolved_id != ref:
            try:
                image = client.images.get(resolved_id)
                usage_count, usage_refs = _collect_managed_image_usage(client)
                registry_records = list_managed_image_records()
                detail = _serialize_image(
                    image,
                    usage_count=usage_count.get(image.id, 0),
                    usage_refs=usage_refs.get(image.id, []),
                    registry_record=registry_records.get(image.id),
                )
                detail["attrs"] = getattr(image, "attrs", None) or {}
                return detail
            except docker.errors.ImageNotFound:
                unregister_managed_image(resolved_id)
        raise ContainerServiceError(f"未找到指定受管镜像: {ref}", 404)
    except docker.errors.APIError as exc:
        raise ContainerServiceError(f"获取受管镜像详情失败: {_docker_error_message(exc)}", 500)


def pull_image(image: str, app_config: AppConfig = None) -> Dict[str, Any]:
    if app_config is None:
        app_config = default_config

    requested_image = str(image or "").strip()
    if not requested_image:
        raise ValidationError("镜像名称不能为空")

    resolved_image = _resolve_image_reference(requested_image, getattr(app_config, "IMAGE_SOURCE", None))
    client = _ensure_client()

    try:
        image_obj = client.images.pull(resolved_image)
        if isinstance(image_obj, list):
            image_obj = image_obj[-1] if image_obj else client.images.get(resolved_image)
        record = register_managed_image(
            image_obj.id,
            source="manual-pull",
            requested_image=requested_image,
            resolved_image=resolved_image,
            tags=list(getattr(image_obj, "tags", None) or []),
        )
        usage_count, usage_refs = _collect_managed_image_usage(client)
        payload = _serialize_image(
            image_obj,
            usage_count=usage_count.get(image_obj.id, 0),
            usage_refs=usage_refs.get(image_obj.id, []),
            registry_record=record,
        )
        payload["requested_image"] = requested_image
        payload["resolved_image"] = resolved_image
        return payload
    except docker.errors.ImageNotFound:
        _raise_pull_error("not found", requested_image, resolved_image, 404)
    except docker.errors.APIError as exc:
        _raise_pull_error(_docker_error_message(exc), requested_image, resolved_image, 500)


def pull_image_streaming(image: str, app_config: AppConfig = None):
    """流式拉取镜像，逐行返回进度日志，最后返回镜像详情字典。"""
    if app_config is None:
        app_config = default_config

    requested_image = str(image or "").strip()
    if not requested_image:
        raise ValidationError("镜像名称不能为空")

    resolved_image = _resolve_image_reference(requested_image, getattr(app_config, "IMAGE_SOURCE", None))
    repository, tag = _split_image_reference(resolved_image)
    if not repository:
        raise ValidationError("镜像名称不能为空")

    client = _ensure_client()

    yield f"正在解析镜像: {resolved_image}"
    try:
        for chunk in client.api.pull(repository=repository, tag=tag, stream=True, decode=True):
            if not isinstance(chunk, dict):
                continue

            if chunk.get("error"):
                message = str(chunk.get("error") or "").strip()
                _raise_pull_error(message or "未知错误", requested_image, resolved_image, 500)

            line = _format_pull_progress_event(chunk)
            if line:
                yield line

        try:
            image_obj = client.images.get(resolved_image)
        except docker.errors.ImageNotFound:
            image_obj = client.images.pull(resolved_image)
            if isinstance(image_obj, list):
                image_obj = image_obj[-1] if image_obj else client.images.get(resolved_image)

        record = register_managed_image(
            image_obj.id,
            source="manual-pull",
            requested_image=requested_image,
            resolved_image=resolved_image,
            tags=list(getattr(image_obj, "tags", None) or []),
        )
        usage_count, usage_refs = _collect_managed_image_usage(client)
        payload = _serialize_image(
            image_obj,
            usage_count=usage_count.get(image_obj.id, 0),
            usage_refs=usage_refs.get(image_obj.id, []),
            registry_record=record,
        )
        payload["requested_image"] = requested_image
        payload["resolved_image"] = resolved_image
        yield payload
    except ContainerServiceError:
        raise
    except docker.errors.APIError as exc:
        _raise_pull_error(_docker_error_message(exc), requested_image, resolved_image, 500)


def delete_image(image_ref: str, force: bool = False) -> Dict[str, Any]:
    ref = str(image_ref or "").strip()
    if not ref:
        raise ValidationError("镜像标识不能为空")

    client = _ensure_client()
    try:
        registry_records = list_managed_image_records()
        managed_usage_count, _managed_usage_refs = _collect_managed_image_usage(client)
        resolved_id = resolve_registered_image_ref(ref)
        image = client.images.get(resolved_id or ref)
        if image.id not in registry_records and managed_usage_count.get(image.id, 0) <= 0:
            raise ContainerServiceError(f"未找到指定受管镜像: {ref}", 404)
        image_id = str(getattr(image, "id", "") or ref)
        tags = _normalize_tags((getattr(image, "attrs", None) or {}).get("RepoTags"))
        client.images.remove(image=resolved_id or ref, force=bool(force), noprune=False)
        unregister_managed_image(image_id)
        return {
            "image": ref,
            "id": image_id,
            "tags": tags,
            "deleted": True,
            "force": bool(force),
        }
    except docker.errors.ImageNotFound:
        resolved_id = resolve_registered_image_ref(ref)
        if resolved_id:
            unregister_managed_image(resolved_id)
        raise ContainerServiceError(f"未找到指定受管镜像: {ref}", 404)
    except docker.errors.APIError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        code = 409 if status_code == 409 else 500
        raise ContainerServiceError(f"删除受管镜像失败: {_docker_error_message(exc)}", code)


def prune_images() -> Dict[str, Any]:
    client = _ensure_client()
    try:
        registry_records = list_managed_image_records()
        usage_count, _usage_refs = _collect_managed_image_usage(client)
        deleted_items = []
        reclaimed = 0

        for image_id in list(registry_records.keys()):
            if usage_count.get(image_id, 0) > 0:
                continue
            try:
                image = client.images.get(image_id)
            except docker.errors.ImageNotFound:
                unregister_managed_image(image_id)
                continue

            payload = _serialize_image(image, usage_count=0, usage_refs=[], registry_record=registry_records.get(image_id))
            if not payload.get("is_dangling"):
                continue

            reclaimed += int(payload.get("size_bytes") or 0)
            image_tags = payload.get("tags") or []
            client.images.remove(image=image_id, force=False, noprune=False)
            unregister_managed_image(image_id)
            deleted_items.append(image_id)
            deleted_items.extend([tag for tag in image_tags if tag not in deleted_items])

        return {
            "deleted": deleted_items,
            "deleted_count": len(deleted_items),
            "space_reclaimed": reclaimed,
            "space_reclaimed_text": _format_bytes(reclaimed),
            "scope": "managed",
        }
    except docker.errors.APIError as exc:
        raise ContainerServiceError(f"清理受管悬空镜像失败: {_docker_error_message(exc)}", 500)