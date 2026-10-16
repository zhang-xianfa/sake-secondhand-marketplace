# app/routes/index.py
from flask import Blueprint, render_template, request
# 【修改点1-1：新增导入】导入 db
from app.models import Goods, Category, db # 导入 db

bp = Blueprint('index', __name__)

@bp.route('/')
def index():
    # 获取分⻚参数
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    price_max = request.args.get('price_max', type=float)
    condition = request.args.get('condition')
    # 【修改点1-2：使用 db.joinedload(Goods.images) 预加载图片】
    query = Goods.query.options(db.joinedload(Goods.images))

    keyword = request.args.get('q')
    if keyword:
        query = query.filter(Goods.title.contains(keyword) | Goods.description.contains(keyword))
        goods = query.paginate(page=page, per_page=5)
        categories = Category.query.all()
        return render_template('index.html', goods=goods, categories=categories)

    if category_id:
        # 按分类筛选
        query = query.filter_by(category_id=category_id)
    if price_max:
        # 按最⾼价筛选
        query = query.filter(Goods.price <= price_max)
    if condition:
        # 按成⾊筛选
        query = query.filter_by(condition=condition)
        # 进⾏分⻚查询
    goods = query.paginate(page=page, per_page=15)
    categories = Category.query.all()

    return render_template('index.html', goods=goods, categories=categories)
