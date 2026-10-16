import os

from dotenv import load_dotenv

load_dotenv()

# 数据库连接：默认本地 MySQL，可用环境变量 DATABASE_URL 覆盖
SQLALCHEMY_DATABASE_URI = os.environ.get(
    'DATABASE_URL',
    'mysql+pymysql://root:root@localhost:3306/campus_market?charset=utf8mb4'
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# 生产环境请务必通过环境变量 SECRET_KEY 覆盖
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-change-me')

# 静态文件上传路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
GOODS_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'goods_images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
