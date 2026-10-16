from flask_migrate import Migrate
from app import create_app, db

app = create_app()
migrate = Migrate(app, db)

# 关键: 使用 Flask 原生 CLI 插件 (不要用 flask_script)
# 现在你可以直接用 flask db 命令进行迁移
