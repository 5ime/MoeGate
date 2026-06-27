"""应用配置"""
import ipaddress
import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from core.version import VERSION as PACKAGE_VERSION

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

    # WebUI Basic 认证（两者均配置时启用）
    WEBUI_BASIC_AUTH_USER: Optional[str] = os.getenv("WEBUI_BASIC_AUTH_USER")
    WEBUI_BASIC_AUTH_PASSWORD: Optional[str] = os.getenv("WEBUI_BASIC_AUTH_PASSWORD")

    # Prometheus 指标
    ENABLE_PUBLIC_METRICS: bool = _get_bool_env("ENABLE_PUBLIC_METRICS", False)
    METRICS_TOKEN: Optional[str] = os.getenv("METRICS_TOKEN")

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
    MAX_CONTAINER_ENV_KEYS: int = _get_int_env("MAX_CONTAINER_ENV_KEYS", 64)
    MAX_CONTAINER_ENV_VALUE_LEN: int = _get_int_env("MAX_CONTAINER_ENV_VALUE_LEN", 4096)
    CONTAINER_MEMORY_LIMIT: str = os.getenv("CONTAINER_MEMORY_LIMIT", "512m")
    CONTAINER_CPU_LIMIT: Optional[float] = _get_float_env_optional("CONTAINER_CPU_LIMIT")
    CONTAINER_CPU_SHARES: Optional[int] = _get_int_env_optional("CONTAINER_CPU_SHARES")
    IMAGE_SOURCE: Optional[str] = os.getenv("IMAGE_SOURCE")
    WEBUI_API_BASE: Optional[str] = os.getenv("WEBUI_API_BASE")
    WEBUI_POLL_INTERVAL_SEC: int = _get_int_env("WEBUI_POLL_INTERVAL_SEC", 30)
    COMPOSE_MANAGED_SUBNET_POOL: str = os.getenv("COMPOSE_MANAGED_SUBNET_POOL", "172.30.0.0/16")
    COMPOSE_MANAGED_SUBNET_PREFIX: int = _get_int_env("COMPOSE_MANAGED_SUBNET_PREFIX", 24)

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
    FRP_LOCAL_IP: str = os.getenv("FRP_LOCAL_IP", "127.0.0.1")

    # 安全
    API_KEY: Optional[str] = os.getenv("API_KEY")
    ENABLE_API_SESSION_COOKIE: bool = _get_bool_env("ENABLE_API_SESSION_COOKIE", True)
    API_SESSION_COOKIE_NAME: str = os.getenv("API_SESSION_COOKIE_NAME", "moegate_session")
    API_SESSION_TTL_SEC: int = _get_int_env("API_SESSION_TTL_SEC", 86400)
    API_SESSION_COOKIE_SECURE: bool = _get_bool_env("API_SESSION_COOKIE_SECURE", False)
    API_SESSION_COOKIE_SAMESITE: str = os.getenv("API_SESSION_COOKIE_SAMESITE", "Lax")
    API_SESSION_SECRET: Optional[str] = os.getenv("API_SESSION_SECRET")
    ENABLE_API_CSRF: bool = _get_bool_env("ENABLE_API_CSRF", True)
    API_CSRF_COOKIE_NAME: str = os.getenv("API_CSRF_COOKIE_NAME", "moegate_csrf")
    API_CSRF_HEADER_NAME: str = os.getenv("API_CSRF_HEADER_NAME", "X-CSRF-Token")
    ALLOWED_BASE_DIR: Optional[str] = os.getenv("ALLOWED_BASE_DIR")
    RUNTIME_STORE_PERSIST: bool = _get_bool_env("RUNTIME_STORE_PERSIST", False)

    # 限流 / 超时
    RATE_LIMIT_PER_MIN: int = _get_int_env("RATE_LIMIT_PER_MIN", 60)
    AUTH_FAILURE_LIMIT_PER_MIN: int = _get_int_env("AUTH_FAILURE_LIMIT_PER_MIN", 10)
    REQUEST_TIMEOUT: int = _get_int_env("REQUEST_TIMEOUT", 30)
    RATE_LIMIT_MAX_TRACKED_KEYS: int = _get_int_env("RATE_LIMIT_MAX_TRACKED_KEYS", 10000)
    RATE_LIMIT_GC_INTERVAL_SECONDS: int = _get_int_env("RATE_LIMIT_GC_INTERVAL_SECONDS", 30)

    # SSE（流式构建日志）
    SSE_MAX_LOG_LINE_LENGTH: int = _get_int_env("SSE_MAX_LOG_LINE_LENGTH", 2000)
    SSE_MAX_LOG_EVENTS: int = _get_int_env("SSE_MAX_LOG_EVENTS", 2000)

    # 反向代理 / CORS
    TRUST_PROXY_HEADERS: bool = _get_bool_env("TRUST_PROXY_HEADERS", False)
    TRUSTED_PROXY_IPS: list = field(default_factory=lambda: _get_csv_env("TRUSTED_PROXY_IPS"))
    CORS_ALLOWED_ORIGINS: list = field(default_factory=lambda: _get_csv_env("CORS_ALLOWED_ORIGINS"))

    # 运行态 API 是否禁止超过 .env 启动值的配额（MAX_CONTAINERS / MAX_RENEW_TIMES）
    LOCK_RUNTIME_QUOTA_TO_BOOT: bool = _get_bool_env("LOCK_RUNTIME_QUOTA_TO_BOOT", True)

    # 告警 Webhook
    ALERT_WEBHOOK_URL: Optional[str] = os.getenv("ALERT_WEBHOOK_URL")
    ALERT_WEBHOOK_TIMEOUT: int = _get_int_env("ALERT_WEBHOOK_TIMEOUT", 5)

    # 日志
    LOG_LEVEL: Optional[str] = os.getenv("LOG_LEVEL")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text").strip().lower()
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    LOG_MAX_SIZE: str = os.getenv("LOG_MAX_SIZE", "10MB")
    LOG_BACKUP_COUNT: int = _get_int_env("LOG_BACKUP_COUNT", 5)

    # 关闭时是否销毁所有受管容器（生产环境建议关闭）
    SHUTDOWN_DESTROY_CONTAINERS: bool = _get_bool_env("SHUTDOWN_DESTROY_CONTAINERS", False)

    # 容器到期 reconcile 扫描间隔（秒）
    EXPIRE_RECONCILE_INTERVAL_SEC: int = _get_int_env("EXPIRE_RECONCILE_INTERVAL_SEC", 60)

    # Docker
    DISABLE_DOCKER_CREDENTIALS: bool = _get_bool_env("DISABLE_DOCKER_CREDENTIALS", False)

    # Compose 启动策略：ctf（默认，允许 privileged 等）| strict（生产加固，拒绝高危配置）
    COMPOSE_POLICY: str = os.getenv("COMPOSE_POLICY", "ctf").strip().lower() or "ctf"

    # Compose 不支持字段的处理：warn（记录/API 提示）| error（拒绝启动）
    COMPOSE_UNSUPPORTED: str = os.getenv("COMPOSE_UNSUPPORTED", "warn").strip().lower() or "warn"

    # 多实例共享 ALLOWED_BASE_DIR 时，通过文件锁协调容器名额预留
    ENABLE_SHARED_QUOTA: bool = _get_bool_env("ENABLE_SHARED_QUOTA", True)

    # 由 __post_init__ 解析，供 middleware/ip 使用
    TRUSTED_PROXY_NETWORKS: List[object] = field(default_factory=list, init=False, repr=False)

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

        if self.MAX_CONTAINER_ENV_KEYS <= 0:
            raise ValueError("MAX_CONTAINER_ENV_KEYS 必须大于 0")
        if self.MAX_CONTAINER_ENV_VALUE_LEN <= 0:
            raise ValueError("MAX_CONTAINER_ENV_VALUE_LEN 必须大于 0")

        if self.AUTH_FAILURE_LIMIT_PER_MIN <= 0:
            raise ValueError("AUTH_FAILURE_LIMIT_PER_MIN 必须大于 0")

        if self.WEBUI_POLL_INTERVAL_SEC <= 0:
            raise ValueError("WEBUI_POLL_INTERVAL_SEC 必须大于 0")

        try:
            compose_pool = ipaddress.ip_network(self.COMPOSE_MANAGED_SUBNET_POOL, strict=False)
        except ValueError:
            raise ValueError("COMPOSE_MANAGED_SUBNET_POOL 必须是合法的 IPv4 CIDR 网段")
        if compose_pool.version != 4:
            raise ValueError("COMPOSE_MANAGED_SUBNET_POOL 目前仅支持 IPv4 网段")
        self.COMPOSE_MANAGED_SUBNET_POOL = str(compose_pool)

        if self.COMPOSE_MANAGED_SUBNET_PREFIX < compose_pool.prefixlen:
            raise ValueError("COMPOSE_MANAGED_SUBNET_PREFIX 不能小于 COMPOSE_MANAGED_SUBNET_POOL 的前缀长度")
        if self.COMPOSE_MANAGED_SUBNET_PREFIX > 30:
            raise ValueError("COMPOSE_MANAGED_SUBNET_PREFIX 不能大于 30")

        port_range = self.MAX_PORT - self.MIN_PORT
        if port_range < self.MAX_CONTAINERS:
            raise ValueError(
                f"端口范围 ({port_range}) 小于最大容器数 ({self.MAX_CONTAINERS})，可能导致端口不足"
            )

        # API 认证
        if not self.API_KEY or self.API_KEY == "your_secret_api_key":
            raise ValueError("必须配置有效的 API_KEY，且不能使用默认占位值")

        if self.ENABLE_API_SESSION_COOKIE:
            if not self.API_SESSION_SECRET or self.API_SESSION_SECRET == self.API_KEY:
                raise ValueError(
                    "启用 Cookie Session 时必须配置独立的 API_SESSION_SECRET，"
                    "且不能与 API_KEY 相同"
                )

        if not str(self.API_CSRF_COOKIE_NAME or "").strip():
            raise ValueError("API_CSRF_COOKIE_NAME 不能为空")
        if not str(self.API_CSRF_HEADER_NAME or "").strip():
            raise ValueError("API_CSRF_HEADER_NAME 不能为空")

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

        self.RATE_LIMIT_BACKEND = "memory"
        if self.ALERT_WEBHOOK_TIMEOUT <= 0:
            raise ValueError("ALERT_WEBHOOK_TIMEOUT 必须大于 0")

        self.TRUSTED_PROXY_NETWORKS = self._parse_trusted_proxy_networks()

        if not self.DEBUG:
            if self.ENABLE_PUBLIC_METRICS and not str(self.METRICS_TOKEN or "").strip():
                raise ValueError(
                    "生产环境启用 ENABLE_PUBLIC_METRICS 时必须配置 METRICS_TOKEN"
                )
            if self.TRUST_PROXY_HEADERS and not self.TRUSTED_PROXY_IPS:
                raise ValueError(
                    "生产环境启用 TRUST_PROXY_HEADERS 时必须配置 TRUSTED_PROXY_IPS"
                )
            if len(str(self.API_KEY or "")) < 32:
                raise ValueError(
                    "生产环境 API_KEY 长度不足 32 字符，请使用高熵随机密钥"
                )

        if self.EXPIRE_RECONCILE_INTERVAL_SEC <= 0:
            raise ValueError("EXPIRE_RECONCILE_INTERVAL_SEC 必须大于 0")

        if self.LOG_FORMAT not in ("text", "json"):
            raise ValueError("LOG_FORMAT 仅支持 text 或 json")

        if self.COMPOSE_POLICY not in ("ctf", "strict"):
            raise ValueError("COMPOSE_POLICY 仅支持 ctf 或 strict")

        if self.COMPOSE_UNSUPPORTED not in ("warn", "error"):
            raise ValueError("COMPOSE_UNSUPPORTED 仅支持 warn 或 error")

        self._log_production_warnings()

    def _parse_trusted_proxy_networks(self) -> List[object]:
        """将 TRUSTED_PROXY_IPS 解析为 ip_network 列表（支持单 IP 与 CIDR）。"""
        networks: List[object] = []
        for raw in self.TRUSTED_PROXY_IPS or []:
            text = str(raw or "").strip()
            if not text:
                continue
            try:
                if "/" in text:
                    networks.append(ipaddress.ip_network(text, strict=False))
                else:
                    addr = ipaddress.ip_address(text)
                    prefix = 32 if addr.version == 4 else 128
                    networks.append(ipaddress.ip_network(f"{addr}/{prefix}", strict=False))
            except ValueError as exc:
                raise ValueError(f"TRUSTED_PROXY_IPS 含非法地址: {text}") from exc
        return networks

    def _log_production_warnings(self) -> None:
        """非调试模式下提示常见生产误配（L3–L5）。"""
        if self.DEBUG:
            return
        if self.TRUST_PROXY_HEADERS:
            if self.TRUSTED_PROXY_IPS:
                logger.warning(
                    "TRUST_PROXY_HEADERS 已启用：仅当直连来源 IP 属于 TRUSTED_PROXY_IPS 时"
                    "才读取 X-Forwarded-For / X-Real-IP"
                )
            else:
                logger.warning(
                    "TRUST_PROXY_HEADERS 已启用但未配置 TRUSTED_PROXY_IPS："
                    "将忽略代理头并使用 request.remote_addr（调试模式允许）"
                )
        if self.HOST in ("0.0.0.0", "::"):
            logger.warning(
                "API_HOST=%s：服务监听所有网卡，请配合防火墙限制 %s 端口访问",
                self.HOST,
                self.PORT,
            )
        if self.ENABLE_API_SESSION_COOKIE and not self.API_SESSION_COOKIE_SECURE:
            logger.warning(
                "API_SESSION_COOKIE_SECURE=false：HTTPS 生产环境应设为 true，"
                "否则 Session Cookie 可能经明文 HTTP 传输"
            )


try:
    config = AppConfig()
    logger.info("配置加载成功")
except ValueError as e:
    logger.error("配置验证失败: %s", e)
    raise
except Exception as e:
    logger.exception("配置加载失败: %s", e)
    raise
