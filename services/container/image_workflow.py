"""镜像拉取与构建工作流。"""
import logging
import os
import random
import types
from contextlib import contextmanager
from typing import List, Optional

import docker

from config.settings import AppConfig, config as default_config
from core.exceptions import DockerConnectionError, ImageBuildError
from infra.docker import ensure_client
from utils.docker_image import (
    extract_docker_error_message,
    format_pull_error_message,
    format_pull_progress_event,
    resolve_image_reference,
    split_image_reference,
)
from utils.image_registry import register_managed_image

logger = logging.getLogger(__name__)


def _raise_pull_image_error(message: str, requested_image: str, resolved_image: str):
    _, error_message = format_pull_error_message(message, requested_image, resolved_image)
    raise ImageBuildError(error_message)


def ensure_image_available(
    image: str,
    app_config: AppConfig = None,
    client=None,
    progress_messages: Optional[List[str]] = None,
):
    """确保镜像在本地可用；缺失时自动拉取。"""
    if app_config is None:
        app_config = default_config

    if client is None:
        client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    requested_image = str(image or "").strip()
    image_source = getattr(app_config, "IMAGE_SOURCE", None)
    resolved_image = resolve_image_reference(image, image_source)

    try:
        image_obj = client.images.get(resolved_image)
        register_managed_image(
            image_obj.id,
            source="managed-container",
            requested_image=requested_image,
            resolved_image=resolved_image,
            tags=list(getattr(image_obj, "tags", None) or []),
        )
        return resolved_image, image_obj
    except docker.errors.ImageNotFound:
        logger.info("镜像 %s 不存在，开始自动拉取", resolved_image)
        if progress_messages is not None:
            progress_messages.append(f"镜像不存在，正在自动拉取: {resolved_image}")
    except docker.errors.APIError as e:
        raise ImageBuildError(f"获取镜像失败: {extract_docker_error_message(e)}")

    try:
        image_obj = client.images.pull(resolved_image)
        if isinstance(image_obj, list):
            image_obj = image_obj[-1] if image_obj else client.images.get(resolved_image)
        logger.info("镜像拉取成功: %s", resolved_image)
        register_managed_image(
            image_obj.id,
            source="managed-container",
            requested_image=requested_image,
            resolved_image=resolved_image,
            tags=list(getattr(image_obj, "tags", None) or []),
        )
        if progress_messages is not None:
            progress_messages.append(f"镜像拉取完成: {resolved_image}")
        return resolved_image, image_obj
    except docker.errors.ImageNotFound:
        _raise_pull_image_error("not found", requested_image, resolved_image)
    except docker.errors.APIError as e:
        _raise_pull_image_error(extract_docker_error_message(e), requested_image, resolved_image)


def ensure_image_available_streaming(
    image: str,
    app_config: AppConfig = None,
    client=None,
):
    """流式确保镜像可用；逐行产生日志，结束时返回(resolved_image, image_obj)。"""
    if app_config is None:
        app_config = default_config

    if client is None:
        client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    requested_image = str(image or "").strip()
    image_source = getattr(app_config, "IMAGE_SOURCE", None)
    resolved_image = resolve_image_reference(image, image_source)

    try:
        image_obj = client.images.get(resolved_image)
        register_managed_image(
            image_obj.id,
            source="managed-container",
            requested_image=requested_image,
            resolved_image=resolved_image,
            tags=list(getattr(image_obj, "tags", None) or []),
        )
        yield f"镜像已存在，本地可用: {resolved_image}"
        return resolved_image, image_obj
    except docker.errors.ImageNotFound:
        logger.info("镜像 %s 不存在，开始自动拉取", resolved_image)
        yield f"镜像不存在，正在自动拉取: {resolved_image}"
    except docker.errors.APIError as e:
        raise ImageBuildError(f"获取镜像失败: {extract_docker_error_message(e)}")

    api_pull = getattr(getattr(client, "api", None), "pull", None)
    if not callable(api_pull):
        progress_messages: List[str] = []
        resolved_image, image_obj = ensure_image_available(
            image,
            app_config=app_config,
            client=client,
            progress_messages=progress_messages,
        )
        for line in progress_messages:
            if line != f"镜像不存在，正在自动拉取: {resolved_image}":
                yield line
        return resolved_image, image_obj

    repository, tag = split_image_reference(resolved_image)
    try:
        for chunk in api_pull(repository=repository, tag=tag, stream=True, decode=True):
            if not isinstance(chunk, dict):
                continue

            if chunk.get("error"):
                _raise_pull_image_error(str(chunk.get("error") or "").strip(), requested_image, resolved_image)

            line = format_pull_progress_event(chunk)
            if line:
                yield line

        try:
            image_obj = client.images.get(resolved_image)
        except docker.errors.ImageNotFound:
            image_obj = client.images.pull(resolved_image)
            if isinstance(image_obj, list):
                image_obj = image_obj[-1] if image_obj else client.images.get(resolved_image)

        register_managed_image(
            image_obj.id,
            source="managed-container",
            requested_image=requested_image,
            resolved_image=resolved_image,
            tags=list(getattr(image_obj, "tags", None) or []),
        )
        yield f"镜像拉取完成: {resolved_image}"
        return resolved_image, image_obj
    except docker.errors.ImageNotFound:
        _raise_pull_image_error("not found", requested_image, resolved_image)
    except docker.errors.APIError as e:
        _raise_pull_image_error(extract_docker_error_message(e), requested_image, resolved_image)


@contextmanager
def disable_docker_credentials(client):
    """临时禁用 docker 凭证存储，避免构建阶段触发外部凭证助手。"""
    original_auth_configs = None
    original_get_all_credentials = None
    try:
        if hasattr(client.api, "_auth_configs"):
            auth_configs = client.api._auth_configs
            original_auth_configs = auth_configs
            if hasattr(auth_configs, "get_all_credentials"):
                original_get_all_credentials = auth_configs.get_all_credentials

            def disabled_get_all_credentials(self):
                return {}

            auth_configs.get_all_credentials = types.MethodType(disabled_get_all_credentials, auth_configs)
            if hasattr(auth_configs, "_store"):
                auth_configs._store = None
            if hasattr(auth_configs, "_creds_store"):
                auth_configs._creds_store = None
            logger.debug("已禁用 Docker 凭证存储（context manager）")
    except Exception as e:
        logger.warning("禁用凭证存储失败（将继续构建）: %s", e)
    try:
        yield
    finally:
        if original_auth_configs is not None and original_get_all_credentials is not None:
            try:
                if hasattr(client.api, "_auth_configs"):
                    auth_configs = client.api._auth_configs
                    auth_configs.get_all_credentials = original_get_all_credentials
            except Exception as restore_err:
                logger.warning("恢复凭证配置时出现警告: %s", restore_err)


def build_or_get_image(path: str, tag: Optional[str], dockerfile: Optional[str] = None):
    """构建或获取 Docker 镜像。"""
    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    path = os.path.normpath(path)

    if os.path.isfile(path):
        path = os.path.dirname(path)

    if not os.path.exists(path):
        raise ImageBuildError(f"构建路径不存在: {path}")

    if not os.path.isdir(path):
        raise ImageBuildError(f"构建路径不是目录: {path}")

    if tag:
        try:
            image = client.images.get(tag)
            logger.info("使用已存在的镜像: %s", tag)
            register_managed_image(
                image.id,
                source="build",
                requested_image=tag,
                resolved_image=tag,
                tags=list(getattr(image, "tags", None) or []),
            )
            return image
        except docker.errors.ImageNotFound:
            logger.info("镜像 %s 不存在，开始构建", tag)

    final_tag = tag or f"dynamic-container-{random.randint(100000, 999999)}"
    logger.info("开始构建镜像: %s, 路径: %s", final_tag, path)

    use_disable_creds = getattr(default_config, "DISABLE_DOCKER_CREDENTIALS", False)
    context_mgr = disable_docker_credentials(client) if use_disable_creds else contextmanager(lambda: (yield))()
    build_kwargs: dict = {"path": path, "tag": final_tag, "rm": True, "forcerm": True}
    if dockerfile:
        build_kwargs["dockerfile"] = dockerfile
    with context_mgr:
        try:
            image, _ = client.images.build(**build_kwargs)
        except docker.errors.BuildError as e:
            error_msg = str(e)
            build_log = ""
            if hasattr(e, "build_log") and e.build_log:
                build_log = "\n".join([log.get("stream", "") for log in e.build_log if log.get("stream")])
                if build_log:
                    error_msg = f"{error_msg}\n构建日志:\n{build_log[-500:]}"
            logger.error("镜像构建失败: %s", error_msg)
            raise ImageBuildError(f"构建镜像失败: {error_msg}")
        except docker.errors.APIError as e:
            error_msg = f"Docker API错误: {str(e)}"
            logger.error(error_msg)
            raise ImageBuildError(error_msg)
        except Exception as e:
            error_msg = f"构建镜像时发生未知错误: {str(e)}"
            logger.exception(error_msg)
            raise ImageBuildError(error_msg)

        logger.info("镜像构建成功: %s", final_tag)
        register_managed_image(
            image.id,
            source="build",
            requested_image=final_tag,
            resolved_image=final_tag,
            tags=list(getattr(image, "tags", None) or []),
        )
        return image


def build_or_get_image_streaming(path: str, tag: Optional[str], dockerfile: Optional[str] = None):
    """构建或获取 Docker 镜像，以生成器方式逐行返回构建日志。"""
    client = ensure_client()
    if not client:
        raise DockerConnectionError("Docker客户端不可用")

    path = os.path.normpath(path)
    if os.path.isfile(path):
        path = os.path.dirname(path)
    if not os.path.exists(path):
        raise ImageBuildError(f"构建路径不存在: {path}")
    if not os.path.isdir(path):
        raise ImageBuildError(f"构建路径不是目录: {path}")

    if tag:
        try:
            client.images.get(tag)
            yield f"镜像 {tag} 已存在，跳过构建"
            yield "__IMAGE_READY__"
            return
        except docker.errors.ImageNotFound:
            yield f"镜像 {tag} 不存在，开始构建..."

    final_tag = tag or f"dynamic-container-{random.randint(100000, 999999)}"
    yield f"开始构建镜像: {final_tag}"

    use_disable_creds = getattr(default_config, "DISABLE_DOCKER_CREDENTIALS", False)
    context_mgr = disable_docker_credentials(client) if use_disable_creds else contextmanager(lambda: (yield))()
    build_kwargs: dict = {"path": path, "tag": final_tag, "rm": True, "forcerm": True, "decode": True}
    if dockerfile:
        build_kwargs["dockerfile"] = dockerfile
    with context_mgr:
        try:
            resp = client.api.build(**build_kwargs)
            for chunk in resp:
                if "stream" in chunk:
                    line = chunk["stream"].rstrip("\n")
                    if line:
                        yield line
                if "error" in chunk:
                    raise ImageBuildError(f"构建镜像失败: {chunk['error']}")
        except ImageBuildError:
            raise
        except docker.errors.BuildError as e:
            error_msg = str(e)
            if hasattr(e, "build_log") and e.build_log:
                build_log = "\n".join([log.get("stream", "") for log in e.build_log if log.get("stream")])
                if build_log:
                    error_msg = f"{error_msg}\n构建日志:\n{build_log[-500:]}"
            raise ImageBuildError(f"构建镜像失败: {error_msg}")
        except docker.errors.APIError as e:
            raise ImageBuildError(f"Docker API错误: {str(e)}")
        except Exception as e:
            raise ImageBuildError(f"构建镜像时发生未知错误: {str(e)}")

    yield f"镜像构建成功: {final_tag}"
    yield "__IMAGE_READY__"
