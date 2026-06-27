"""容器创建元数据 → Docker labels 映射。"""
from typing import Any, Dict, Optional

_LABEL_MAX_LEN = 128
_REQUEST_ID_MAX_LEN = 64


def build_creation_meta_labels(meta: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """将 API 请求 _meta 转为可写入容器 labels 的键值（供 CTF 平台追溯）。"""
    labels: Dict[str, str] = {}
    if not isinstance(meta, dict):
        return labels

    created_by = str(meta.get("created_by") or "").strip()
    if created_by:
        labels["moegate.created_by"] = created_by[:_LABEL_MAX_LEN]

    request_id = str(meta.get("request_id") or "").strip()
    if request_id:
        labels["moegate.request_id"] = request_id[:_REQUEST_ID_MAX_LEN]

    source_ip = str(meta.get("source_ip") or "").strip()
    if source_ip:
        labels["moegate.source_ip"] = source_ip[:_LABEL_MAX_LEN]

    return labels
