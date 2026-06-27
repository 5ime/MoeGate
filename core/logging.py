"""日志配置"""
import json
import logging
import re
from datetime import datetime, timezone
from config import config

logger = logging.getLogger(__name__)


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
    handlers.append(console_handler)

    if config.LOG_FILE:
        try:
            from logging.handlers import RotatingFileHandler

            max_bytes = 10 * 1024 * 1024
            if config.LOG_MAX_SIZE:
                size_match = re.match(r'(\d+)([KMGT]?B?)', config.LOG_MAX_SIZE.upper())
                if size_match:
                    size_value = int(size_match.group(1))
                    size_unit = size_match.group(2) or 'B'
                    multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
                    max_bytes = size_value * multipliers.get(size_unit, 1)

            file_handler = RotatingFileHandler(
                config.LOG_FILE,
                maxBytes=max_bytes,
                backupCount=config.LOG_BACKUP_COUNT,
                encoding='utf-8',
            )
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
            logger.info("文件日志已启用: %s (最大: %s, 备份: %d)",
                        config.LOG_FILE, config.LOG_MAX_SIZE, config.LOG_BACKUP_COUNT)
        except Exception as e:
            logger.warning("配置文件日志失败: %s，将只使用控制台日志", e)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)
    for lib in ('docker', 'urllib3', 'requests'):
        logging.getLogger(lib).setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING if not config.DEBUG else logging.INFO)
