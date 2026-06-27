import logging
import os
import uuid
from flask import Flask, send_from_directory, g, request
from flask_cors import CORS
from werkzeug.utils import safe_join
from config import config
from core.responses import error
from core.exceptions import ContainerServiceError
from core.logging import configure_logging
from routes import api_bp
from utils.static_assets import verify_static_build_info

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
    static_dir = os.path.join(src_dir, 'static')
    if os.path.exists(os.path.join(static_dir, 'index.html')):
        logger.info("使用静态目录: %s", static_dir)
    else:
        logger.warning("静态目录缺少 index.html: %s", static_dir)
    return static_dir


def create_app():
    """创建Flask应用实例"""
    static_dir = None
    if getattr(config, "ENABLE_WEBUI", True):
        static_dir = resolve_web_static_dir()
        verify_static_build_info(static_dir)
    app = Flask(__name__, static_folder=static_dir, static_url_path='/static' if static_dir else None)

    _configure_cors(app)
    configure_logging()
    from services import runtime_store
    runtime_store.reset_session()
    _register_request_id_hook(app)
    _register_health_route(app)
    _register_metrics_route(app)
    _register_webui_auth_hook(app)
    _register_event_handlers()
    app.register_blueprint(api_bp)
    _register_error_handlers(app)
    if static_dir:
        _register_static_routes(app, static_dir)
    else:
        logger.info("WebUI 已禁用（ENABLE_WEBUI=False），仅提供 API")

    if should_start_background_workers():
        from utils.container_manager import get_container_manager
        manager = get_container_manager()
        manager.reconcile_managed_containers()
        manager.start_reconcile_worker()
    else:
        logger.debug("跳过后台 worker 启动（Werkzeug reloader 父进程）")

    return app


def _register_request_id_hook(app):
    @app.before_request
    def assign_request_id():
        incoming = request.headers.get("X-Request-Id")
        g.request_id = (incoming.strip()[:64] if incoming else str(uuid.uuid4())[:8])

    @app.after_request
    def attach_request_id(response):
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-Id"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if not config.DEBUG:
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'",
            )
        return response


def _register_health_route(app):
    from infra.docker import ensure_client

    @app.route("/healthz", methods=["GET"])
    def healthz():
        """公开探活端点（无需 API Key）；仅返回状态码，避免泄露组件细节。"""
        try:
            client = ensure_client()
            if client:
                client.ping()
                return "", 200
        except Exception:
            pass
        return "", 503


def _register_metrics_route(app):
    from core.metrics import render_prometheus_metrics
    from middleware.metrics_auth import check_metrics_access, metrics_endpoint_enabled

    if not metrics_endpoint_enabled():
        return

    @app.route("/metrics", methods=["GET"])
    def public_metrics():
        denied = check_metrics_access()
        if denied is not None:
            return denied
        return render_prometheus_metrics()

    logger.info("已启用 /metrics 端点（public=%s, token=%s）", config.ENABLE_PUBLIC_METRICS, bool(config.METRICS_TOKEN))


def _register_webui_auth_hook(app):
    from middleware.webui_auth import check_webui_basic_auth, webui_auth_enabled

    if not webui_auth_enabled():
        return

    @app.before_request
    def enforce_webui_basic_auth():
        denied = check_webui_basic_auth()
        if denied is not None:
            return denied

    logger.info("已启用 WebUI Basic 认证（用户: %s）", config.WEBUI_BASIC_AUTH_USER)


def _configure_cors(app):
    allowed_origins = list(config.CORS_ALLOWED_ORIGINS or [])
    if config.DEBUG and not allowed_origins:
        allowed_origins = [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]

    if allowed_origins:
        CORS(app, resources={
            r"/api/v1/*": {
                "origins": allowed_origins,
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-API-Key",
                    "X-CSRF-Token",
                    "X-Metrics-Token",
                ],
                "supports_credentials": True,
            }
        })
        logger.info("已启用 CORS 白名单: %s", allowed_origins)
    elif config.DEBUG:
        logger.warning("调试模式未配置 CORS_ALLOWED_ORIGINS，仅允许本地 Vite 开发源")
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
        from services.frp.event_handler import handle_container_created
        get_event_bus().subscribe('container.created', handle_container_created)


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
