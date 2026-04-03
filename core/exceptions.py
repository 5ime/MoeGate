"""自定义异常类"""


class ContainerServiceError(Exception):
    """容器服务基础异常"""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DockerConnectionError(ContainerServiceError):
    def __init__(self, message: str = "Docker服务不可用"):
        super().__init__(message, 503)


class ContainerLimitExceededError(ContainerServiceError):
    def __init__(self, current: int, max_count: int):
        super().__init__(f"容器数量已达上限 ({current}/{max_count})", 429)


class ContainerNotFoundError(ContainerServiceError):
    def __init__(self, container_id: str):
        super().__init__(f"未找到指定容器: {container_id}", 404)


class ValidationError(ContainerServiceError):
    def __init__(self, message: str):
        super().__init__(message, 400)


class InvalidPathError(ContainerServiceError):
    def __init__(self, message: str):
        super().__init__(f"路径验证失败: {message}", 400)


class PortUnavailableError(ContainerServiceError):
    def __init__(self, message: str = "没有可用端口"):
        super().__init__(message, 503)


class ImageBuildError(ContainerServiceError):
    def __init__(self, message: str):
        super().__init__(f"镜像构建失败: {message}", 500)


class MaxRenewTimesExceededError(ContainerServiceError):
    def __init__(self, container_id: str, current: int, max_times: int):
        super().__init__("容器续期次数已达上限，无法续期", 400)
