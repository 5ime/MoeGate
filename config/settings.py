"""应用配置"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 应用版本
try:
    from core.version import VERSION as PACKAGE_VERSION  # type: ignore
except Exception:
    PACKAGE_VERSION = "0.1.0"

load_dotenv()


def _get_int_env(key: str, default: int) -> int:
    try:
        value = os.getenv(key)
        return int(value) if value else default
    except (ValueError, TypeError) as e:
        logger.warning("环境变量 %s 的值无法转换为整数，使用默认值 %d: %s", key, default, e)
        return default


def _get_int_env_optional(key: str, default: Optional[int] = None) -> Optional[int]:
    value = os.getenv(key)
    if not value:
        return default
    try:
        return int(value)
    except (ValueError, TypeError) as e:
        logger.warning("环境变量 %s 的值无法转换为整数，使用默认值 %s: %s", key, default, e)
        return default


def _get_bool_env(key: str, default: bool = False) -> bool:
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def _get_float_env_optional(key: str, default: Optional[float] = None) -> Optional[float]:
    value = os.getenv(key)
    if not value:
        return default
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        logger.warning("环境变量 %s 的值无法转换为浮点数，使用默认值 %s: %s", key, default, e)
        return default


def _get_csv_env(key: str, default: Optional[str] = None) -> list:
    raw = os.getenv(key, default or "")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class AppConfig:
    """应用配置类，从环境变量加载并在初始化时验证。"""

    # 应用版本
    APP_VERSION: str = PACKAGE_VERSION

    # WebUI 面板开关（关闭后不注册静态路由，仅提供 API）
    ENABLE_WEBUI: bool = _get_bool_env("ENABLE_WEBUI", True)

    # 服务
    PORT: int = _get_int_env("API_PORT", 8080)
    HOST: str = os.getenv("API_HOST", "0.0.0.0")
    DEBUG: bool = _get_bool_env("API_DEBUG", False)

    # 容器
    MAX_TIME: int = _get_int_env("MAX_TIME", 3600)
    MAX_CONTAINERS: int = _get_int_env("MAX_CONTAINERS", 30)
    MIN_PORT: int = _get_int_env("MIN_PORT", 20000)
    MAX_PORT: int = _get_int_env("MAX_PORT", 30000)
    MAX_RENEW_TIMES: int = _get_int_env("MAX_RENEW_TIMES", 3)
    CONTAINER_MEMORY_LIMIT: str = os.getenv("CONTAINER_MEMORY_LIMIT", "512m")
    CONTAINER_CPU_LIMIT: Optional[float] = _get_float_env_optional("CONTAINER_CPU_LIMIT")
    CONTAINER_CPU_SHARES: Optional[int] = _get_int_env_optional("CONTAINER_CPU_SHARES")
    IMAGE_SOURCE: Optional[str] = os.getenv("IMAGE_SOURCE")
    WEBUI_API_BASE: Optional[str] = os.getenv("WEBUI_API_BASE")
    WEBUI_POLL_INTERVAL_SEC: int = _get_int_env("WEBUI_POLL_INTERVAL_SEC", 30)

    # FRP
    ENABLE_FRP: bool = _get_bool_env("ENABLE_FRP", False)
    FRP_SERVER_ADDR: Optional[str] = os.getenv("FRP_SERVER_ADDR")
    FRP_SERVER_PORT: int = _get_int_env("FRP_SERVER_PORT", 7000)
    FRP_ADMIN_IP: str = os.getenv("FRP_ADMIN_IP", "127.0.0.1")
    FRP_ADMIN_PORT: int = _get_int_env("FRP_ADMIN_PORT", 7400)
    FRP_ADMIN_ADDR: str = field(init=False)
    FRP_ADMIN_USER: Optional[str] = os.getenv("FRP_ADMIN_USER")
    FRP_ADMIN_PASSWORD: Optional[str] = os.getenv("FRP_ADMIN_PASSWORD")
    FRP_DOMAIN_SUFFIX: Optional[str] = os.getenv("FRP_DOMAIN_SUFFIX")
    FRP_USE_DOMAIN: bool = _get_bool_env("FRP_USE_DOMAIN", False)
    FRP_VHOST_HTTP_PORT: Optional[int] = _get_int_env_optional("FRP_VHOST_HTTP_PORT", None)

    # 安全
    API_KEY: Optional[str] = os.getenv("API_KEY")
    ALLOWED_BASE_DIR: Optional[str] = os.getenv("ALLOWED_BASE_DIR")

    # 限流 / 超时
    RATE_LIMIT_PER_MIN: int = _get_int_env("RATE_LIMIT_PER_MIN", 60)
    REQUEST_TIMEOUT: int = _get_int_env("REQUEST_TIMEOUT", 30)
    RATE_LIMIT_MAX_TRACKED_KEYS: int = _get_int_env("RATE_LIMIT_MAX_TRACKED_KEYS", 10000)
    RATE_LIMIT_GC_INTERVAL_SECONDS: int = _get_int_env("RATE_LIMIT_GC_INTERVAL_SECONDS", 30)

    # SSE（流式构建日志）
    SSE_MAX_LOG_LINE_LENGTH: int = _get_int_env("SSE_MAX_LOG_LINE_LENGTH", 2000)
    SSE_MAX_LOG_EVENTS: int = _get_int_env("SSE_MAX_LOG_EVENTS", 2000)

    # 反向代理 / CORS
    TRUST_PROXY_HEADERS: bool = _get_bool_env("TRUST_PROXY_HEADERS", False)
    CORS_ALLOWED_ORIGINS: list = field(default_factory=lambda: _get_csv_env("CORS_ALLOWED_ORIGINS"))

    # 分布式（已移除 Redis，以下参数保留占位但不启用外部后端）
    ALERT_WEBHOOK_URL: Optional[str] = os.getenv("ALERT_WEBHOOK_URL")
    ALERT_WEBHOOK_TIMEOUT: int = _get_int_env("ALERT_WEBHOOK_TIMEOUT", 5)

    # 日志
    LOG_LEVEL: Optional[str] = os.getenv("LOG_LEVEL")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    LOG_MAX_SIZE: str = os.getenv("LOG_MAX_SIZE", "10MB")
    LOG_BACKUP_COUNT: int = _get_int_env("LOG_BACKUP_COUNT", 5)

    # 性能监控
    ENABLE_PERFORMANCE_MONITORING: bool = _get_bool_env("ENABLE_PERFORMANCE_MONITORING", False)
    PERFORMANCE_LOG_INTERVAL: int = _get_int_env("PERFORMANCE_LOG_INTERVAL", 300)
    ALERT_CPU_THRESHOLD: int = _get_int_env("ALERT_CPU_THRESHOLD", 95)
    ALERT_CPU_SUSTAINED_INTERVALS: int = _get_int_env("ALERT_CPU_SUSTAINED_INTERVALS", 3)
    ALERT_COOLDOWN_SEC: int = _get_int_env("ALERT_COOLDOWN_SEC", 900)
    ALERT_MEM_THRESHOLD: int = _get_int_env("ALERT_MEM_THRESHOLD", 90)
    ALERT_MEM_SUSTAINED_INTERVALS: int = _get_int_env("ALERT_MEM_SUSTAINED_INTERVALS", 3)

    # 运行时配置写入
    # 为安全起见，生产建议关闭（即使 API_KEY 泄露，也避免持久化篡改 .env）
    ALLOW_RUNTIME_CONFIG_WRITE: bool = _get_bool_env("ALLOW_RUNTIME_CONFIG_WRITE", False)

    # Docker
    DISABLE_DOCKER_CREDENTIALS: bool = _get_bool_env("DISABLE_DOCKER_CREDENTIALS", False)

    def __post_init__(self):
        # 端口范围
        if self.MIN_PORT >= self.MAX_PORT:
            raise ValueError("MIN_PORT 必须小于 MAX_PORT")
        if self.MIN_PORT < 1024:
            raise ValueError("MIN_PORT 应该大于等于 1024（避免使用系统保留端口）")
        if self.MAX_PORT > 65535:
            raise ValueError("MAX_PORT 不能超过 65535")

        # 容器数量
        if self.MAX_CONTAINERS <= 0:
            raise ValueError("MAX_CONTAINERS 必须大于 0")
        if self.MAX_CONTAINERS > 1000:
            raise ValueError("MAX_CONTAINERS 不应超过 1000（建议值）")

        # 时间
        if self.MAX_TIME <= 0:
            raise ValueError("MAX_TIME 必须大于 0")
        if self.MAX_TIME > 86400 * 7:
            raise ValueError("MAX_TIME 不应超过 7 天")

        if self.MAX_RENEW_TIMES < 0:
            raise ValueError("MAX_RENEW_TIMES 不能为负数")

        if self.WEBUI_POLL_INTERVAL_SEC <= 0:
            raise ValueError("WEBUI_POLL_INTERVAL_SEC 必须大于 0")

        port_range = self.MAX_PORT - self.MIN_PORT
        if port_range < self.MAX_CONTAINERS:
            raise ValueError(
                f"端口范围 ({port_range}) 小于最大容器数 ({self.MAX_CONTAINERS})，可能导致端口不足"
            )

        # API 认证
        if not self.API_KEY or self.API_KEY == "your_secret_api_key":
            raise ValueError("必须配置有效的 API_KEY，且不能使用默认占位值")

        # 路径白名单
        if not self.ALLOWED_BASE_DIR:
            raise ValueError("必须配置 ALLOWED_BASE_DIR 以限制容器构建路径")
        if os.path.isabs(self.ALLOWED_BASE_DIR):
            resolved = self.ALLOWED_BASE_DIR
        else:
            src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            resolved = os.path.join(src_root, self.ALLOWED_BASE_DIR)
        self.ALLOWED_BASE_DIR = os.path.abspath(resolved)
        if not os.path.isdir(self.ALLOWED_BASE_DIR):
            raise ValueError(f"ALLOWED_BASE_DIR 不存在或不是目录: {self.ALLOWED_BASE_DIR}")

        # FRP
        if self.ENABLE_FRP:
            if not self.FRP_SERVER_ADDR:
                raise ValueError("启用FRP时必须配置 FRP_SERVER_ADDR")
            if self.FRP_USE_DOMAIN and not self.FRP_DOMAIN_SUFFIX:
                raise ValueError("使用域名访问时必须配置 FRP_DOMAIN_SUFFIX")

        # 规范化域名后缀：允许填写 ".example.com" 或 "example.com"，内部统一存为 "example.com"
        if self.FRP_DOMAIN_SUFFIX is not None:
            suffix = str(self.FRP_DOMAIN_SUFFIX).strip()
            if not suffix:
                self.FRP_DOMAIN_SUFFIX = None
            else:
                # 拒绝带协议/路径的输入，避免误配置
                lowered = suffix.lower()
                if lowered.startswith("http://") or lowered.startswith("https://") or "/" in suffix:
                    raise ValueError("FRP_DOMAIN_SUFFIX 仅允许填写域名后缀，如 example.com（不包含协议/路径）")
                # 去掉前导点与尾部点
                suffix = suffix.lstrip(".").rstrip(".")
                self.FRP_DOMAIN_SUFFIX = suffix or None
        self.FRP_ADMIN_ADDR = f"http://{self.FRP_ADMIN_IP}:{self.FRP_ADMIN_PORT}"

        # CPU
        if self.CONTAINER_CPU_LIMIT is not None and self.CONTAINER_CPU_LIMIT <= 0:
            raise ValueError("CONTAINER_CPU_LIMIT 必须大于 0")
        if self.CONTAINER_CPU_SHARES is not None and self.CONTAINER_CPU_SHARES < 0:
            raise ValueError("CONTAINER_CPU_SHARES 不能为负数")

        # 限流 / 超时
        if self.RATE_LIMIT_PER_MIN <= 0:
            raise ValueError("RATE_LIMIT_PER_MIN 必须大于 0")
        if self.REQUEST_TIMEOUT <= 0:
            raise ValueError("REQUEST_TIMEOUT 必须大于 0")
        if self.RATE_LIMIT_MAX_TRACKED_KEYS <= 0:
            raise ValueError("RATE_LIMIT_MAX_TRACKED_KEYS 必须大于 0")
        if self.RATE_LIMIT_GC_INTERVAL_SECONDS <= 0:
            raise ValueError("RATE_LIMIT_GC_INTERVAL_SECONDS 必须大于 0")
        if self.SSE_MAX_LOG_LINE_LENGTH <= 0:
            raise ValueError("SSE_MAX_LOG_LINE_LENGTH 必须大于 0")
        if self.SSE_MAX_LOG_EVENTS <= 0:
            raise ValueError("SSE_MAX_LOG_EVENTS 必须大于 0")

        # 限流后端固定为内存实现（已移除 Redis 支持）
        self.RATE_LIMIT_BACKEND = "memory"
        if self.ALERT_WEBHOOK_TIMEOUT <= 0:
            raise ValueError("ALERT_WEBHOOK_TIMEOUT 必须大于 0")

        if self.ENABLE_PERFORMANCE_MONITORING and self.PERFORMANCE_LOG_INTERVAL <= 0:
            raise ValueError("PERFORMANCE_LOG_INTERVAL 必须大于 0")
        if self.ALERT_CPU_THRESHOLD <= 0 or self.ALERT_CPU_THRESHOLD > 100:
            raise ValueError("ALERT_CPU_THRESHOLD 必须在 1-100 之间")
        if self.ALERT_CPU_SUSTAINED_INTERVALS <= 0:
            raise ValueError("ALERT_CPU_SUSTAINED_INTERVALS 必须大于 0")
        if self.ALERT_COOLDOWN_SEC < 0:
            raise ValueError("ALERT_COOLDOWN_SEC 不能为负数")
        if self.ALERT_MEM_THRESHOLD <= 0 or self.ALERT_MEM_THRESHOLD > 100:
            raise ValueError("ALERT_MEM_THRESHOLD 必须在 1-100 之间")
        if self.ALERT_MEM_SUSTAINED_INTERVALS <= 0:
            raise ValueError("ALERT_MEM_SUSTAINED_INTERVALS 必须大于 0")


try:
    config = AppConfig()
    logger.info("配置加载成功")
except ValueError as e:
    logger.error("配置验证失败: %s", e)
    raise
except Exception as e:
    logger.exception("配置加载失败: %s", e)
    raise
