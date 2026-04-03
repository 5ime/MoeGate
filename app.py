import logging
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from werkzeug.utils import safe_join
from config import config
from core.responses import error
from core.exceptions import ContainerServiceError
from core.logging import configure_logging
from workers.performance import start_performance_monitoring
from routes import api_bp

logger = logging.getLogger(__name__)

_ALLOWED_STATIC_EXT = frozenset({
    '.html', '.css', '.js', '.map', '.json', '.png', '.jpg', '.jpeg',
    '.gif', '.svg', '.ico', '.webp', '.woff', '.woff2', '.ttf', '.webmanifest',
})


def should_start_background_workers() -> bool:
    if not config.DEBUG:
        return True
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def resolve_web_static_dir() -> str:
    src_dir = os.path.dirname(__file__)
    legacy_static_dir = os.path.join(src_dir, 'static')
    vue_dist_dir = os.path.join(src_dir, 'frontend', 'dist')

    if os.path.exists(os.path.join(legacy_static_dir, 'index.html')):
        logger.info("使用静态目录: %s", legacy_static_dir)
        return legacy_static_dir
    if os.path.exists(os.path.join(vue_dist_dir, 'index.html')):
        logger.info("使用前端构建产物目录: %s", vue_dist_dir)
        return vue_dist_dir
    logger.info("默认使用静态目录: %s", legacy_static_dir)
    return legacy_static_dir


def create_app():
    """创建Flask应用实例"""
    static_dir = None
    if getattr(config, "ENABLE_WEBUI", True):
        static_dir = resolve_web_static_dir()
    app = Flask(__name__, static_folder=static_dir, static_url_path='/static' if static_dir else None)

    _configure_cors(app)
    configure_logging()
    _register_event_handlers()
    app.register_blueprint(api_bp)
    _register_error_handlers(app)
    if static_dir:
        _register_static_routes(app, static_dir)
    else:
        logger.info("WebUI 已禁用（ENABLE_WEBUI=False），仅提供 API")

    start_performance_monitoring()

    return app


def _configure_cors(app):
    if config.DEBUG:
        CORS(app)
    else:
        allowed_origins = config.CORS_ALLOWED_ORIGINS
        if allowed_origins:
            CORS(app, resources={
                r"/api/v1/*": {
                    "origins": allowed_origins,
                    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
                }
            })
            logger.info("已启用生产CORS白名单: %s", allowed_origins)
        else:
            logger.warning("生产模式未配置 CORS_ALLOWED_ORIGINS，默认不放开浏览器跨域访问")


def _register_static_routes(app, static_dir):
    @app.route('/')
    def index():
        return send_from_directory(static_dir, 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        if path.startswith('api/'):
            return error("接口不存在", 404)
        if path.startswith('static/'):
            relative_path = path[7:]
            # 使用 werkzeug 的 safe_join 防止路径穿越/反斜杠/编码绕过
            if safe_join(static_dir, relative_path) is None:
                return error("非法路径", 400)
            ext = os.path.splitext(relative_path)[1].lower()
            if not ext or ext not in _ALLOWED_STATIC_EXT:
                return error("静态资源不存在", 404)
            return send_from_directory(static_dir, relative_path)
        return send_from_directory(static_dir, 'index.html')


def _register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return error("请求参数错误", 400)

    @app.errorhandler(404)
    def not_found(e):
        return error("接口不存在", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error("请求方法不允许", 405)

    @app.errorhandler(413)
    def payload_too_large(e):
        return error("请求体过大", 413)

    @app.errorhandler(429)
    def too_many_requests(e):
        return error("请求过于频繁，请稍后再试", 429)

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("服务器内部错误")
        return error("服务器内部错误", 500)

    @app.errorhandler(503)
    def service_unavailable(e):
        return error("服务暂时不可用", 503)

    @app.errorhandler(ContainerServiceError)
    def handle_container_error(exc):
        logger.warning("容器服务错误: %s (code: %d)", exc.message, exc.code)
        return error(exc.message, exc.code)

    @app.errorhandler(Exception)
    def handle_generic_error(exc):
        logger.exception("未处理的异常")
        return error("服务器内部错误", 500)


def _register_event_handlers():
    from core.events import get_event_bus
    from utils.container_manager import get_container_manager
    from utils.destroy import destroy_container

    manager = get_container_manager()
    manager.register_destroy_callback(destroy_container)
    logger.info("容器自动销毁回调已注册")

    if config.ENABLE_FRP:
        from services.frp import create_config
        get_event_bus().subscribe('container.created', create_config)


app = create_app()

if __name__ == "__main__":
    from core.shutdown import setup_signal_handlers, graceful_shutdown

    setup_signal_handlers()
    logger.info("启动服务器 - Host: %s, Port: %s, Debug: %s", config.HOST, config.PORT, config.DEBUG)
    logger.info("配置信息 - 最大容器数: %s, FRP启用: %s", config.MAX_CONTAINERS, config.ENABLE_FRP)

    if config.DEBUG:
        logger.warning("当前运行在调试模式，不适合生产环境")

    try:
        app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT, threaded=True)
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
        graceful_shutdown()
    except Exception:
        logger.exception("应用启动失败")
        graceful_shutdown()
        raise
