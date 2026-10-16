# SAKE —— 校园二手交易平台

基于 Flask 的校园二手交易平台，覆盖商品发布、站内私信、订单支付、信用评价的完整闭环。

## 一、功能

| 模块 | 说明 |
|---|---|
| 用户认证 | 注册、登录、登出，基于 Flask-Login 的会话管理与登录态保护 |
| 商品 | 发布（多图上传）、详情、编辑、删除、收藏、上架 / 下架 |
| 留言与回复 | 商品页一级留言 + 二级回复（自关联树形结构）、点赞 |
| 私信 | 基于 WebSocket 的实时一对一聊天，按「用户对 + 商品」建立会话上下文 |
| 订单与支付 | 下单、模拟支付、订单状态流转（pending → paid → completed / canceled） |
| 信用评价 | 订单完成后买卖双方互评 1~5 星，用户主页展示平均分与评价数 |
| 通知中心 | 留言、回复、私信、订单等事件的站内通知与未读计数 |
| 后台管理 | 管理员对分类、商品、留言的删除与维护 |

## 二、技术栈

- **Web 框架**：Flask 2.3 + 蓝图（Blueprint）分模块组织路由
- **数据库**：MySQL + SQLAlchemy 2.0（ORM），Flask-Migrate（Alembic）管理迁移
- **实时通信**：Flask-SocketIO，用户登录后加入以自己 id 命名的房间，消息定向推送
- **认证**：Flask-Login
- **模板**：Jinja2，`base.html` 统一布局，其余页面继承
- **文件上传**：本地存储，白名单校验扩展名（png / jpg / jpeg / gif），限制 16MB

## 三、数据模型

共 11 张表，核心关系如下：

```
User ──┬──< Goods ──< GoodsImage          # 一个商品多张图
       ├──< Message ──< Message            # 自关联：一级留言 / 二级回复
       │      └──< MessageLike             # 留言点赞（联合唯一约束防重复）
       ├──< Order ──── Payment             # 订单一对一支付记录
       │      └─── Review                  # 订单一对一评价
       ├──< Conversation ──< PrivateMessage # 私信会话与消息
       ├──< Notification                   # 通知（区分留言 / 私信类型）
       └──< favorites >── Goods            # 多对多收藏
```

几个值得说明的设计：

- **留言的树形结构**用单表自关联实现，`parent_id` 为 `NULL` 表示一级留言，
  通过 `remote_side` 定义反向关系 `replies`。
- **会话唯一性**由 `(user1_id, user2_id, goods_id)` 联合唯一约束保证，
  避免同一对用户针对同一商品重复建会话。
- **通知表**的 `recipient_id` / `sender_id` 都外键指向 `users.id`，
  因此两处关系都必须显式声明 `foreign_keys`，否则 SQLAlchemy 无法确定连接条件。
- **平均评分**用 `@property` 在模型上实时计算，而非冗余存储，避免评价增删时不一致。

## 四、目录结构

```
sake-secondhand-marketplace/
├── app/
│   ├── __init__.py              # 应用工厂：注册蓝图、初始化 db/login/socketio
│   ├── models.py                # 全部数据模型
│   └── routes/
│       ├── index.py             # 首页商品展示与筛选
│       ├── auth.py              # 注册 / 登录 / 登出
│       ├── goods.py             # 商品发布、详情、收藏、留言、点赞、上下架
│       ├── user_center.py       # 个人中心：我的发布 / 留言 / 收藏
│       ├── profile.py           # 个人信息编辑与头像上传
│       ├── chat.py              # 私信会话与实时聊天
│       ├── notification.py      # 通知中心
│       ├── payment.py           # 订单创建与模拟支付
│       └── admin.py             # 后台管理
├── migrations/                  # Alembic 迁移脚本
├── templates/                   # 21 个 Jinja2 模板
├── static/                      # 样式、图标与上传目录
├── config.py                    # 配置（支持环境变量覆盖）
├── manage.py                    # Flask CLI 入口
├── run.py                       # 启动脚本（含 SocketIO）
├── .env.example                 # 环境变量模板
└── requirements.txt
```

## 五、运行

### 1. 准备数据库

```sql
CREATE DATABASE campus_market DEFAULT CHARSET utf8mb4;
```

### 2. 配置

```bash
cp .env.example .env      # 按需修改 DATABASE_URL 与 SECRET_KEY
pip install -r requirements.txt
```

### 3. 初始化并启动

```bash
flask db upgrade          # 建表
python run.py             # 默认监听 0.0.0.0:5000
```

## 六、说明

- 本仓库为整理版，**已移除**开发环境的虚拟环境、缓存与用户上传的图片；
  数据库连接串与会话密钥改为从环境变量读取，原硬编码值不再保留。
- 上传目录 `static/uploads/` 保留空结构，运行时按需写入。
