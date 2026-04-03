"""响应格式化工具"""
import logging
from typing import Any
from flask import jsonify
from core.exceptions import ContainerServiceError

logger = logging.getLogger(__name__)


def success(data: Any = None, message: str = "成功", code: int = 200):
    response = {"code": code, "msg": message}
    if data is not None:
        response["data"] = data
    return jsonify(response), code


def error(message: str, code: int = 500):
    response = {"code": code, "msg": message}
    try:
        status = int(code)
    except Exception:
        status = 500

    # 4xx 多为用户请求问题，不应刷爆 error；5xx 才是服务端故障
    if 400 <= status < 500:
        logger.warning("API错误 [%d]: %s", status, message)
    else:
        logger.error("API错误 [%d]: %s", status, message)
    return jsonify(response), code


def exception(exc):
    if isinstance(exc, ContainerServiceError):
        return error(exc.message, exc.code)
    logger.exception("未处理的异常: %s", exc)
    return error("服务器内部错误", 500)
