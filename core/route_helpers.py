"""路由层通用辅助函数。"""
from core.exceptions import ContainerServiceError
from core.responses import exception, success


def handle_service_call(func, success_message: str = "操作成功", success_code: int = 200, *args, **kwargs):
    """调用服务函数并统一封装响应。"""
    try:
        data = func(*args, **kwargs)
        return success(data, success_message, code=success_code)
    except ContainerServiceError as exc:
        return exception(exc)
