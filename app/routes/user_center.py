# app/routes/user_center.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

# 【修改点2-1：新增导入】导入 db
from app.models import Goods, Message, db, User  # 导入 db

bp = Blueprint('user_center', __name__, url_prefix='/user')


@bp.route('/')
@login_required
def dashboard():
    # 【修改点2-2：为 my_goods 使用 db.joinedload(Goods.images) 预加载图片】
    my_goods = Goods.query.options(db.joinedload(Goods.images)).filter_by(seller_id=current_user.id).all()
    my_messages = Message.query.filter_by(user_id=current_user.id).all()
    # 查询当前用户的收藏商品
    # 【修改点2-3：为 my_favorites 使用 db.joinedload(Goods.images) 预加载图片】
    # 需要通过 User 的 favorites 关系反向查询 Goods 并加载图片
    # my_favorites = db.session.query(Goods).options(db.joinedload(Goods.images)).join(current_user.favorites).filter(current_user.id == current_user.id).all() # simplified join
    # 或者更直接的，如果 favorites 关系定义了 lazy='dynamic'
    # my_favorites = db.session.query(Goods).options(joinedload(Goods.images)).join(
    #     current_user.favorites  # 直接通过 User 模型定义的 favorites 关系连接
    # ).filter(
    #     User.id == current_user.id  # 确保只查询当前用户的收藏
    # ).all()
    my_favorites = current_user.favorites
    # 考虑到你的 User 模型中 favorites 关系没有设azy='dynamic'，使用上面显式查询的方式更稳妥。

    return render_template(
        'user_center.html',
        my_goods=my_goods,
        my_messages=my_messages,
        my_favorites=my_favorites) # 传递收藏商品到模板
