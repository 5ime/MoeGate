"""路由模块初始化"""
from flask import Blueprint
from routes.auth import bp as auth_bp
from routes.containers import bp as containers_bp
from routes.frp import bp as frp_bp
from routes.images import bp as images_bp
from routes.networks import bp as networks_bp
from routes.system_alerts import bp as system_alerts_bp
from routes.system_settings import bp as system_settings_bp
from routes.system_status import bp as system_status_bp

api_bp = Blueprint("api", __name__)

api_bp.register_blueprint(auth_bp)
api_bp.register_blueprint(containers_bp)
api_bp.register_blueprint(frp_bp)
api_bp.register_blueprint(images_bp)
api_bp.register_blueprint(networks_bp)
api_bp.register_blueprint(system_status_bp)
api_bp.register_blueprint(system_settings_bp)
api_bp.register_blueprint(system_alerts_bp)

__all__ = ['api_bp']

