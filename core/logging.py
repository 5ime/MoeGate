"""日志配置"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from config import config

logger = logging.getLogger(__name__)

# 1KB / 10MB / 1G / 10MiB 都能解析；单位按首字母映射，避免旧实现把 "10M" 当成 10 字节。
_LOG_SIZE_RE = re.compile(r"(\d+)\s*([KMGT]?)I?B?", re.IGNORECASE)
_SIZE_UNITS = {"": 1, "B": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}
_DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024

# 控制字符会把一条日志伪造/拆成多条（用户可控的容器 ID、路径都会进日志）。
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def parse_log_max_size(value) -> tuple:
    """解析 LOG_MAX_SIZE，返回 (bytes, 是否合法)。

    配置写错时不能静默变成 10 字节/0 字节——那会把轮转关掉或把审计文件瞬间写满。
    """
    text = str(value or "").strip()
    if not text:
        return _DEFAULT_LOG_MAX_BYTES, False
    match = _LOG_SIZE_RE.fullmatch(text)
    if not match:
        return _DEFAULT_LOG_MAX_BYTES, False
    amount = int(match.group(1))
    unit = (match.group(2) or "").upper()
    size = amount * _SIZE_UNITS.get(unit, 1)
    if size <= 0:
        return _DEFAULT_LOG_MAX_BYTES, False
    return size, True


def _sanitize_text(text: str) -> str:
    """把换行/Tab 转义成字面量，防止日志行被伪造。"""
    return (
        str(text)
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


class SanitizeLogFilter(logging.Filter):
    """清洗消息中的控制字符（JSON 模式同样受益）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        record.msg = _CONTROL_CHARS.sub("", _sanitize_text(message))
        record.args = ()
        return True


class RequestContextFilter(logging.Filter):
    """给每条日志补 request_id / client_ip，便于与审计、访问日志关联。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from flask import g, has_request_context

            if has_request_context():
                record.request_id = str(getattr(g, "request_id", "") or "")
                from middleware.ip import get_client_ip

                record.client_ip = str(get_client_ip() or "")
        except Exception:
            pass
        return True


class JsonLogFormatter(logging.Formatter):
    """结构化 JSON 日志格式，便于 ELK/Loki 采集。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.funcName and record.funcName != "<module>":
            payload["func"] = f"{record.funcName}:{record.lineno}"
        request_id = getattr(record, "request_id", "")
        if request_id:
            payload["request_id"] = request_id
        client_ip = getattr(record, "client_ip", "")
        if client_ip:
            payload["client_ip"] = client_ip
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _build_formatter() -> logging.Formatter:
    log_format = (getattr(config, "LOG_FORMAT", None) or "text").lower()
    if log_format == "json":
        return JsonLogFormatter()

    if config.DEBUG:
        text_format = (
            '%(asctime)s | %(levelname)-4s | %(name)s | %(funcName)s:%(lineno)d | %(message)s'
        )
    else:
        text_format = '%(asctime)s | %(levelname)-4s | %(message)s'
    return logging.Formatter(text_format, datefmt='%Y-%m-%d %H:%M:%S')


def _attach_filters(handler: logging.Handler) -> None:
    handler.addFilter(RequestContextFilter())
    handler.addFilter(SanitizeLogFilter())


def _rotate_settings() -> tuple:
    max_bytes, valid = parse_log_max_size(config.LOG_MAX_SIZE)
    if not valid:
        logger.warning(
            "LOG_MAX_SIZE=%r 无法解析，已回退为 10MB（支持 10MB/1GB/512KB 等写法）",
            config.LOG_MAX_SIZE,
        )
    backup_count = int(config.LOG_BACKUP_COUNT or 0)
    if backup_count < 1:
        logger.warning(
            "LOG_BACKUP_COUNT=%s 会导致轮转时直接截断当前日志、不留历史，已回退为 5",
            backup_count,
        )
        backup_count = 5
    return max_bytes, backup_count


def _configure_audit_sink(formatter, max_bytes: int, backup_count: int) -> None:
    """把 moegate.audit 输出到独立文件（可选）。

    审计日志是最需要长期保全的数据，不能和普通应用日志一起被
    `LOG_LEVEL=WARNING` 过滤、也不应跟着应用日志轮转被淹没。
    """
    audit_logger = logging.getLogger("moegate.audit")
    audit_logger.setLevel(logging.INFO)
    for handler in list(audit_logger.handlers):
        if getattr(handler, "_moegate_audit_sink", False):
            audit_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    audit_file = config.AUDIT_LOG_FILE
    if not audit_file:
        audit_logger.propagate = True
        return
    try:
        from logging.handlers import RotatingFileHandler

        parent = os.path.dirname(str(audit_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        handler = RotatingFileHandler(
            audit_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        _attach_filters(handler)
        handler._moegate_audit_sink = True
        audit_logger.addHandler(handler)
        # 独立落盘后不再混入应用日志，避免两份不一致的审计副本
        audit_logger.propagate = False
        logger.info("审计日志已独立落盘: %s", audit_file)
    except Exception as exc:
        audit_logger.propagate = True
        logger.warning("配置审计日志失败: %s，将回退到应用日志", exc)


def configure_logging():
    """配置应用日志"""
    if config.LOG_LEVEL:
        log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    else:
        log_level = logging.DEBUG if config.DEBUG else logging.INFO

    formatter = _build_formatter()
    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    _attach_filters(console_handler)
    handlers.append(console_handler)

    max_bytes, backup_count = _rotate_settings()
    file_handler = None
    if config.LOG_FILE:
        try:
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                config.LOG_FILE,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8',
            )
            file_handler.setFormatter(formatter)
            _attach_filters(file_handler)
            handlers.append(file_handler)
        except Exception as e:
            logger.warning("配置文件日志失败: %s，将只使用控制台日志", e)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)
    for lib in ('docker', 'urllib3', 'requests'):
        logging.getLogger(lib).setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING if not config.DEBUG else logging.INFO)
    _configure_audit_sink(formatter, max_bytes, backup_count)
    # 必须在 basicConfig 之后：此前的日志没有 handler，会被直接丢弃。
    if file_handler is not None:
        logger.info(
            "文件日志已启用: %s (最大: %s, 备份: %d)",
            config.LOG_FILE,
            config.LOG_MAX_SIZE,
            getattr(file_handler, "backupCount", 0),
        )
