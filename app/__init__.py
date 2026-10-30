
# app/__init__.py
import os

from flask import Flask,g
# 导入蓝图
# from app.routes.index import bp as index_bp

# 导入SQLAlchemy
# from flask_sqlalchemy import SQLAlchemy
# 导入db对象
from .models import db,Notification
from flask_login import LoginManager,current_user
from flask_socketio import SocketIO

# 要配置LoginManager
login_manager = LoginManager()
socketio = SocketIO()


def create_app():

    # 或者如下写法
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '../templates'),
                static_folder=os.path.join(os.path.dirname(__file__), '../static'))

    # 加载配置文件
    app.config.from_pyfile('../config.py')

    db.init_app(app)  # 关键：将app注册进SQLAlchemy

    login_manager.init_app(app)  # 必须初始化注册login_manager
    socketio.init_app(app)
    login_manager.login_view = 'auth.login'  # 指定登录路由端点名
    login_manager.login_message = '请先登录'  # 可选的自定义消息

    # 注册蓝图
    from app.routes.index import bp as index_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.goods import bp as goods_bp
    from app.routes.user_center import bp as user_center_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.profile import bp as profile_bp
    from app.routes.notification import notification_bp
    from app.routes.chat import bp as chat_bp

    from app.routes.notification import notification_bp as notification_bp
    from app.routes.payment import bp as payment_bp
    app.register_blueprint(index_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(goods_bp)
    app.register_blueprint(user_center_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    # app.register_blueprint(notification_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(payment_bp)


# 确保@login_manager.user_loader装饰器在app/__init__.py，
# 否则 Flask-Login 没法加载⽤户。

    # 全局未读消息提醒
    @app.before_request
    def load_unread_counts():
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(
                recipient_id = current_user.id,
                is_read=False
            ).count()
            current_user.unread_notifications_total = unread_count
        else:
            current_user.unread_notifications_total = 0

    return app



@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))

# 定义一个socketio事件处理器
from flask_socketio import join_room,leave_room,emit

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(str(current_user.id))
        print(f'User {current_user.username} (ID: {current_user.id}) connected to WebSocket and joined room {current_user.id}')
    else:
        print('Unauthenticated user tried to connect to WebSocket.')
        return False

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(str(current_user.id))
        print(f'User{current_user.username} (ID:{current_user.id}) disconnected from WebSocket and left room {current_user.id}')
    else:
        print('Unauthenticated user disconnected from WebSocket.')