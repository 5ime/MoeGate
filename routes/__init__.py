"""路由模块初始化"""
from flask import Blueprint
from routes.containers import bp as containers_bp
from routes.frp import bp as frp_bp
from routes.images import bp as images_bp
from routes.networks import bp as networks_bp
from routes.system import bp as system_bp

# 创建主API蓝图
api_bp = Blueprint("api", __name__)

# 注册所有子蓝图
api_bp.register_blueprint(containers_bp)
api_bp.register_blueprint(frp_bp)
api_bp.register_blueprint(images_bp)
api_bp.register_blueprint(networks_bp)
api_bp.register_blueprint(system_bp)

__all__ = ['api_bp']

