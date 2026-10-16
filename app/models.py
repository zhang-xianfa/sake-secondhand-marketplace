# app/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

# Flask-Login会要求User模型必须实现以下四个属性或⽅法：
# is_authenticated/is_active/is_anonymous/get_id
# UserMixin会⾃动为User模型实现is_authenticated、is_active、
# is_anonymous、get_id()⽅法，避免我们  手手实现


# 增加一个收藏与取消收藏表格，需要定义在User模型之前
favorites = db.Table('favorites',
                     db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
                     db.Column('goods_id', db.Integer, db.ForeignKey('goods.id'))
 )


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    student_id = db.Column(db.String(50))
    # 所属院系
    department = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=True)
    # 头像地址
    avatar = db.Column(db.String(500))
    is_admin = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    # 收藏关系
    favorites = db.relationship('Goods', secondary=favorites, backref='favorited_by')

    # 新增属性：计算用户平均评分
    @property
    def average_rating(self):
        # reviews_received 是 Review 模型中 backref 定义的反向关系
        # 如果用户没有收到任何评价，则返回 0.0
        if self.reviews_received.count() == 0:
            return 0.0
        # 计算所有收到的评价的评分总和
        total_rating = sum([r.rating for r in self.reviews_received.all()])
        # 计算平均分并保留一位小数
        return round(total_rating / self.reviews_received.count(), 1)

    # 新增属性：获取用户收到的评价总数
    @property
    def review_count(self):
        return self.reviews_received.count()


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)


class Goods(db.Model):
    __tablename__ = 'goods'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2))
    # image_url = db.Column(db.String(255))

    # 商品信息: 九成新、八成新
    condition = db.Column(db.String(20))
    is_sold = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联商品分类id与用户id
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    category = db.relationship('Category')
    seller = db.relationship('User')
    # 与 GoodsImage 建立一对多关系
    # 'GoodsImage' 是子模型的类名
    # backref='goods' 将在 GoodsImage 上创建一个 'goods' 属性，指向其关联的 Goods 对象
    # cascade="all, delete-orphan" 确保当 Goods 被删除时，所有关联的 GoodsImage 记录也会被自动删除
    images = db.relationship('GoodsImage', backref='goods', lazy=True, cascade="all, delete-orphan")


# GoodsImage
class GoodsImage(db.Model):
    __tablename__ = 'goods_images'
    id = db.Column(db.Integer, primary_key=True)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)  # 存储图片URL
    order = db.Column(db.Integer, default=0)  # 可以用于排序图片，例如第一张是主图


# app/models.py (修改Message模型)
class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # 新增：父评论ID，用于实现回复功能（None表示是一级评论）
    parent_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)

    goods = db.relationship('Goods')
    user = db.relationship('User')
    # 新增：关联子评论（回复）
    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')


# 在现有模型下方添加
class MessageLike(db.Model):
    __tablename__ = 'message_likes'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 防止重复点赞
    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', name='_message_user_like_uc'),)

    message = db.relationship('Message', backref=db.backref('likes', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('message_likes', lazy='dynamic'))

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                             nullable=True)  # 明确设置为 nullable=True

    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                          nullable=True)
    message = db.Column(db.String(255))  # 通知内容
    is_read = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)

    # 关键修改：添加 lazy='dynamic' 使关系返回可查询对象
    recipient = db.relationship(
        'User',
        foreign_keys=[recipient_id],
        backref=db.backref('notifications_received', lazy='dynamic')  # 这里是重点
    )
    sender = db.relationship(
        'User',
        foreign_keys=[sender_id],
        backref=db.backref('sent_notifications', lazy='dynamic')
    )
    # 通知类型，区分留言与私信
    type = db.Column(db.String(50),nullable=False,default='general')
    related_id = db.Column(db.Integer,nullable=True)

    # recipient = db.relationship('User', foreign_keys=[recipient_id], backref = 'notifications_received')
    # sender = db.relationship('User', foreign_keys=[sender_id])



# 会话表
class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # 关联到发起会话的商品，以便提供上下文
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=True)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user1 = db.relationship('User', foreign_keys=[user1_id], backref='conversations_initiated')
    user2 = db.relationship('User', foreign_keys=[user2_id], backref='conversations_received')
    goods = db.relationship('Goods')
    __table_args__ = (db.UniqueConstraint('user1_id','user2_id','goods_id',name='_user_pair_goods_uc'),)


# 私信表
class PrivateMessage(db.Model):
    __tablename__ = 'private_messages'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)  # 标记消息是否已读

    conversation = db.relationship('Conversation', backref='messages')
    sender = db.relationship('User', foreign_keys=[sender_id])

# app/models.py 新增以下模型
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)  # 订单编号
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # 订单金额
    status = db.Column(db.String(20), default='pending')  # pending/paid/completed/canceled
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    paid_time = db.Column(db.DateTime)  # 支付时间
    completed_time = db.Column(db.DateTime)  # 完成时间
    is_reviewed = db.Column(db.Boolean, default=False) # 【新增字段】：标记订单是否已被评价

    goods = db.relationship('Goods')
    buyer = db.relationship('User', foreign_keys=[buyer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    payment_no = db.Column(db.String(50), unique=True, nullable=False)  # 支付单号
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # 支付金额
    payment_time = db.Column(db.DateTime, nullable=False)  # 支付时间
    payment_method = db.Column(db.String(20))  # 支付方式（alipay/wechat等）

    order = db.relationship('Order', backref='payment')

# 【新增模型】：Review
class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True, nullable=False) # 一个订单只能有一条评价
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # 评价人 (通常是买家)
    reviewed_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # 被评价人 (通常是卖家)
    rating = db.Column(db.Integer, nullable=False) # 1-5 星级评分
    content = db.Column(db.Text, nullable=True) # 评价内容
    create_time = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系定义
    # uselist=False 表示这是一对一关系 (一个订单只有一条评价，一条评价只属于一个订单)
    order = db.relationship('Order', backref=db.backref('review', uselist=False))
    # reviewer: 评价人 (通常是买家), 通过 foreign_keys 指定关联到 User.id
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref=db.backref('reviews_given', lazy='dynamic'))
    # reviewed_user: 被评价人 (通常是卖家), 通过 foreign_keys 指定关联到 User.id
    reviewed_user = db.relationship('User', foreign_keys=[reviewed_user_id], backref=db.backref('reviews_received', lazy='dynamic'))

