"""FRP代理管理"""
import logging
import threading
from typing import Tuple, Dict, Any, Optional, List

from services.frp.client import get_frp_config, update_frp_config
from services.frp.config_document import (
    find_proxy_in_document,
    load_config_document,
    remove_proxy_from_document,
    serialize_config_document,
    upsert_proxy_in_document,
    validate_and_fix_document,
)
from services.frp.utils import generate_proxy_section, get_common_config, normalize_proxy_config
from services.frp.exceptions import FRPConfigError

logger = logging.getLogger(__name__)

_config_update_lock = threading.Lock()


def _base_document(config_content: str) -> Dict[str, Any]:
    data = load_config_document(config_content)
    if data:
        return data
    if config_content and config_content.strip():
        logger.warning("FRP 配置无法解析，将使用通用配置作为基础")
    return load_config_document(get_common_config())


def remove_proxy_from_config(config_content: str, name: str) -> str:
    """从配置内容中移除指定代理配置。"""
    if not name:
        return config_content
    data = _base_document(config_content)
    data = remove_proxy_from_document(data, name)
    return serialize_config_document(data)


def find_proxy_section(config_content: str, name: str) -> Tuple[Optional[str], Optional[str]]:
    """查找指定名称的代理配置段。"""
    if not name:
        return None, "未提供代理名称"

    entry = find_proxy_in_document(_base_document(config_content), name)
    if not entry:
        return None, f"未找到名为 '{name}' 的代理配置"

    return generate_proxy_section(entry).strip(), None


def add_proxy_to_config(config_content: str, proxy_config: Dict[str, Any]) -> str:
    """向配置内容中添加代理配置。"""
    data = validate_and_fix_document(_base_document(config_content))
    data = upsert_proxy_in_document(data, proxy_config)
    return serialize_config_document(data)


def add_proxy_config(proxy_config: Dict[str, Any]) -> Tuple[bool, str]:
    """添加新的代理配置（线程安全）。"""
    try:
        if not proxy_config.get('name') or not proxy_config.get('localPort'):
            return False, "代理配置缺少必要字段: name 和 localPort"

        try:
            proxy_config = normalize_proxy_config(proxy_config)
        except FRPConfigError as e:
            return False, e.message

        proxy_name = proxy_config.get('name')

        with _config_update_lock:
            try:
                current_config = get_frp_config()
            except FRPConfigError as e:
                logger.warning("无法获取当前FRP配置: %s，将生成新配置", e.message)
                current_config = get_common_config()

            new_config = add_proxy_to_config(current_config, proxy_config)

            if proxy_name not in new_config:
                logger.error("代理配置 %s 未添加到新配置中", proxy_name)
                return False, f"代理配置添加失败: {proxy_name} 未找到"

            success, msg = update_frp_config(new_config)

            if success:
                logger.info("成功添加代理配置: %s", proxy_name)
            else:
                logger.error("添加代理配置失败: %s, 错误: %s", proxy_name, msg)
            return success, msg
    except Exception as e:
        logger.exception("添加代理配置失败: %s", e)
        return False, f"添加代理配置失败: {str(e)}"


def add_proxy_configs_batch(proxy_configs: List[Dict[str, Any]]) -> Tuple[int, str]:
    """批量添加代理配置（单次读写 frpc 配置，适合 Compose 多 service）。"""
    valid_configs = [
        cfg for cfg in (proxy_configs or [])
        if cfg.get("name") and cfg.get("localPort")
    ]
    if not valid_configs:
        return 0, "无有效代理配置"

    try:
        with _config_update_lock:
            try:
                current_config = get_frp_config()
            except FRPConfigError as e:
                logger.warning("无法获取当前FRP配置: %s，将生成新配置", e.message)
                current_config = get_common_config()

            new_config = current_config
            added_names: List[str] = []
            for proxy_config in valid_configs:
                proxy_name = proxy_config.get("name")
                new_config = add_proxy_to_config(new_config, proxy_config)
                if proxy_name and proxy_name in new_config:
                    added_names.append(str(proxy_name))

            if not added_names:
                return 0, "代理配置均未写入"

            success, msg = update_frp_config(new_config)
            if success:
                logger.info("批量添加 FRP 代理成功: %s", ", ".join(added_names))
                return len(added_names), msg
            logger.error("批量添加 FRP 代理失败: %s", msg)
            return 0, msg
    except Exception as e:
        logger.exception("批量添加代理配置失败")
        return 0, f"批量添加代理配置失败: {str(e)}"


def update_proxy_config(name: str, proxy_config: Dict[str, Any]) -> Tuple[bool, str]:
    """更新指定代理的配置（线程安全）。"""
    try:
        if not name:
            return False, "代理名称不能为空"

        proxy_config['name'] = name

        try:
            proxy_config = normalize_proxy_config(proxy_config)
        except FRPConfigError as e:
            return False, e.message

        with _config_update_lock:
            current_config = get_frp_config()

            if not find_proxy_in_document(load_config_document(current_config), name):
                return False, f"未找到名为 '{name}' 的代理配置"

            new_config = remove_proxy_from_config(current_config, name)
            new_config = add_proxy_to_config(new_config, proxy_config)

            success, msg = update_frp_config(new_config)
            if success:
                logger.info("成功更新代理配置: %s", name)
            return success, msg
    except Exception as e:
        logger.exception("更新代理配置失败")
        return False, f"更新代理配置失败: {str(e)}"


def delete_container_proxy_configs(container_name: str) -> Tuple[bool, str]:
    """删除容器关联的全部 FRP 代理（含多端口附加代理）。"""
    try:
        if not container_name:
            return False, "容器名称不能为空"

        from services.frp.parser import list_proxies_from_content
        from services.frp.utils import proxy_belongs_to_container

        with _config_update_lock:
            current_config = get_frp_config()
            proxy_names = [
                proxy.get("name")
                for proxy in list_proxies_from_content(current_config)
                if proxy.get("name") and proxy_belongs_to_container(proxy.get("name"), container_name)
            ]
            if not proxy_names:
                return False, f"未找到容器 '{container_name}' 的 FRP 代理配置"

            new_config = current_config
            for proxy_name in proxy_names:
                new_config = remove_proxy_from_config(new_config, proxy_name)

            if not new_config.strip() or 'serverAddr' not in new_config:
                new_config = get_common_config()

            success, msg = update_frp_config(new_config)
            if success:
                logger.info("成功删除容器 %s 的 %d 个 FRP 代理", container_name, len(proxy_names))
            return success, msg
    except Exception as e:
        logger.exception("删除容器 FRP 代理失败")
        return False, f"删除容器 FRP 代理失败: {str(e)}"


def delete_proxy_config(name: str) -> Tuple[bool, str]:
    """删除指定代理的配置（线程安全）。"""
    try:
        if not name:
            return False, "代理名称不能为空"

        with _config_update_lock:
            current_config = get_frp_config()

            if not find_proxy_in_document(load_config_document(current_config), name):
                return False, f"未找到名为 '{name}' 的代理配置"

            new_config = remove_proxy_from_config(current_config, name)
            if not new_config.strip() or 'serverAddr' not in new_config:
                new_config = get_common_config()

            success, msg = update_frp_config(new_config)
            if success:
                logger.info("成功删除代理配置: %s", name)
            return success, msg
    except Exception as e:
        logger.exception("删除代理配置失败")
        return False, f"删除代理配置失败: {str(e)}"
