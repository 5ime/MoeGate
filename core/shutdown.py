"""优雅关闭与信号处理"""
import logging
import signal
import sys
import threading

from config import config

logger = logging.getLogger(__name__)

_shutdown_lock = threading.Lock()
_is_shutting_down = False


def is_shutting_down() -> bool:
    return _is_shutting_down


def graceful_shutdown():
    """关闭应用并清理资源"""
    global _is_shutting_down

    with _shutdown_lock:
        if _is_shutting_down:
            logger.debug("关闭流程已在进行中，跳过重复调用")
            return
        _is_shutting_down = True

    logger.info("开始关闭...")

    from workers.performance import stop_performance_monitoring
    stop_performance_monitoring()

    try:
        from utils.container_manager import get_container_manager
        manager = get_container_manager()
        try:
            manager.cancel_all_timers()
        except Exception as e:
            logger.debug("取消定时器时出现问题: %s", e)
        container_ids = manager.get_container_ids()

        logger.info("正在清理 %d 个容器...", len(container_ids))
        from utils.destroy import destroy_container
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(8, len(container_ids) or 1), thread_name_prefix="shutdown") as pool:
            futures = {pool.submit(destroy_container, cid): cid for cid in container_ids}
            for future in as_completed(futures, timeout=60):
                cid = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error("清理容器 %s 失败: %s", cid, e)
    except Exception as e:
        logger.error("清理容器时发生错误: %s", e)

    logger.info("关闭完成")


def setup_signal_handlers():
    """设置系统信号处理器"""
    def signal_handler(sig, frame):
        logger.info("收到信号 %s，开始关闭...", sig)
        graceful_shutdown()
        sys.exit(0)

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
