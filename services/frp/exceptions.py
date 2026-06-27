"""FRP异常类"""
from core.exceptions import ContainerServiceError


class FRPConfigError(ContainerServiceError):
    """FRP配置相关异常"""
    pass


class FRPPortUnavailableError(FRPConfigError):
    """FRP 远程端口不可用"""

    def __init__(self, container_name: str, min_port: int, max_port: int):
        super().__init__(
            f"FRP 无可用远程端口（容器 {container_name}，范围 {min_port}-{max_port}）",
            code=503,
        )
        self.container_name = container_name
        self.min_port = min_port
        self.max_port = max_port

