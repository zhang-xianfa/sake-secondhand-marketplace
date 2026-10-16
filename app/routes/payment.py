# app/routes/payment.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, Goods, Order, Payment, Review, Notification
from datetime import datetime
import uuid
from sqlalchemy.orm import joinedload # 导入 joinedload

bp = Blueprint('payment', __name__, url_prefix='/payment')

# 支付页面 (保持不变)
@bp.route('/pay/<int:order_id>')
@login_required
def pay(order_id):
    order = Order.query.get_or_404(order_id)

    # 验证订单归属
    if order.buyer_id != current_user.id:
        flash('无权访问此订单', 'danger')
        return redirect(url_for('index.index'))

    # 订单已支付则
    if order.status != 'pending':
        flash('该订单状态异常', 'danger')
        return redirect(url_for('payment.order_detail', order_id=order_id))

    return render_template('payment.html', order=order)


# 模拟支付提交（实际项目中需对接支付接口）
@bp.route('/submit/<int:order_id>', methods=['POST'])
@login_required
def submit_payment(order_id):
    order = Order.query.get_or_404(order_id)

    if order.buyer_id != current_user.id or order.status != 'pending':
        flash('订单状态异常或无权操作', 'danger')
        return redirect(url_for('payment.order_detail', order_id=order_id))

    # 模拟支付成功（实际项目中需调用第三方支付接口）
    payment = Payment(
        order_id=order_id,
        payment_no=f"PAY{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}",
        amount=order.amount,
        payment_time=datetime.utcnow(),
        payment_method=request.form.get('payment_method', 'alipay')
    )

    # 更新订单状态
    order.status = 'paid'
    order.paid_time = datetime.utcnow()

    # 标记商品为已售出
    goods = Goods.query.get(order.goods_id)
    goods.is_sold = True

    db.session.add(payment)
    try:
        db.session.commit()
        flash('支付成功！', 'success')
        # 【修正点1】：支付成功后，重定向到订单详情页
        return redirect(url_for('payment.order_detail', order_id=order.id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"支付提交失败: {str(e)}", exc_info=True)
        flash(f'支付失败: {str(e)}', 'danger')
        return redirect(url_for('payment.pay', order_id=order.id))


# 订单详情 (【修改点2】：预加载评价信息)
@bp.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.options(
        joinedload(Order.goods).joinedload(Goods.images), # 确保加载商品图片
        joinedload(Order.payment), # 加载支付信息
        joinedload(Order.review) # 【新增】：加载评价信息
    ).get_or_404(order_id)

    # 验证权限（买家或卖家可查看）
    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        flash('无权访问此订单', 'danger')
        return redirect(url_for('index.index'))
    return render_template('payment/order_detail.html', order=order)


# 我的订单列表 (保持不变)
@bp.route('/my_orders')
@login_required
def my_orders():
    # 买家订单
    buying_orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.create_time.desc()).all()
    # 卖家订单
    selling_orders = Order.query.filter_by(seller_id=current_user.id).order_by(Order.create_time.desc()).all()
    return render_template('payment/my_orders.html', buying_orders=buying_orders, selling_orders=selling_orders)


# 生成订单页面（跳转到支付页面） (保持不变)
@bp.route('/create/<int:goods_id>', methods=['GET', 'POST'])
@login_required
def create_order(goods_id):
    goods = Goods.query.get_or_404(goods_id)

    # 验证商品状态（未售出且不是自己发布的）
    if goods.is_sold:
        flash('该商品已售出', 'danger')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))
    if goods.seller_id == current_user.id:
        flash('不能购买自己发布的商品', 'danger')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))

    if request.method == 'POST':
        # 创建订单
        order_no = f"ORD{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        new_order = Order(
            order_no=order_no,
            goods_id=goods_id,
            buyer_id=current_user.id,
            seller_id=goods.seller_id,
            amount=goods.price,
            status='pending'  # 待支付
        )
        db.session.add(new_order)
        db.session.commit()  # 先提交订单，确保订单ID已生成


        # 发送通知给卖家
        notification = Notification(
            recipient_id=goods.seller_id,
            message=f"您有一个新的交易订单：{goods.title}",
            type="transaction", # 【新增通知类型】：交易
            related_id=new_order.id,
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()  # 提交通知

        # 跳转到支付页面
        return redirect(url_for('payment.pay', order_id=new_order.id))

    return render_template('payment/create_order.html', goods=goods)


# 【新增路由】：卖家标记订单为完成
@bp.route('/complete_order/<int:order_id>', methods=['POST'])
@login_required
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)

    # 只有卖家能标记订单为完成，且订单状态必须是已支付
    if order.seller_id != current_user.id or order.status != 'paid':
        flash('无权操作或订单状态不正确', 'danger')
        return redirect(url_for('payment.order_detail', order_id=order_id))

    order.status = 'completed'
    order.completed_time = datetime.utcnow()
    db.session.commit()
    flash('订单已成功标记为完成！', 'success')

    # 发送通知给买家，提示其可以评价
    notification = Notification(
        recipient_id=order.buyer_id,
        sender_id=order.seller_id,
        message=f"您购买的商品 '{order.goods.title}' (订单号: {order.order_no}) 已完成，请为卖家 {order.seller.username} 留下评价吧！",
        type="order_completed", # 【新增通知类型】：订单完成
        related_id=order.id,
        is_read=False
    )
    db.session.add(notification)
    db.session.commit()
    # 如果有 SocketIO，可以进一步实时通知买家
    # from app import socketio
    # socketio.emit('new_notification', {'message': notification.message, 'url': url_for('payment.order_detail', order_id=order.id)}, room=str(order.buyer_id))

    return redirect(url_for('payment.order_detail', order_id=order_id))


# 【新增路由】：评价订单 (GET: 显示表单, POST: 提交评价)
@bp.route('/review/<int:order_id>', methods=['GET', 'POST'])
@login_required
def leave_review(order_id):
    order = Order.query.options(joinedload(Order.goods)).get_or_404(order_id)

    # 权限检查：只有买家可以评价自己购买的订单
    if order.buyer_id != current_user.id:
        flash('您无权评价此订单', 'danger')
        return redirect(url_for('payment.my_orders'))

    # 状态检查：订单必须是已完成状态才能评价
    if order.status != 'completed':
        flash('订单尚未完成，无法评价', 'danger')
        return redirect(url_for('payment.order_detail', order_id=order_id))

    # 评价次数检查：一个订单只能评价一次
    if order.is_reviewed:
        flash('您已评价过此订单', 'warning')
        return redirect(url_for('payment.order_detail', order_id=order_id))

    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        content = request.form.get('content', '').strip()

        # 验证评分
        if not rating or not (1 <= rating <= 5):
            flash('请选择1到5星的评分', 'danger')
            return render_template('payment/leave_review.html', order=order)

        # 创建新的评价记录
        review = Review(
            order_id=order.id,
            reviewer_id=current_user.id,
            reviewed_user_id=order.seller_id,
            rating=rating,
            content=content
        )
        db.session.add(review)

        # 标记订单为已评价
        order.is_reviewed = True

        try:
            db.session.commit()
            flash('评价成功！', 'success')

            # 发送通知给卖家，告知收到新评价
            notification_message = f"您收到关于商品 '{order.goods.title}' 的新评价，来自买家 {current_user.username}。"
            notification = Notification(
                recipient_id=order.seller_id,
                sender_id=current_user.id,
                message=notification_message,
                type="new_review", # 【新增通知类型】：新评价
                related_id=order.id, # 关联到订单ID
                is_read=False
            )
            db.session.add(notification)
            db.session.commit()
            # from app import socketio
            # socketio.emit('new_notification', {'message': notification.message, 'url': url_for('payment.order_detail', order_id=order.id)}, room=str(order.seller_id))

            return redirect(url_for('payment.order_detail', order_id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'评价失败: {str(e)}', 'danger')
            current_app.logger.error(f"评价订单失败: {str(e)}", exc_info=True)
            return render_template('payment/leave_review.html', order=order)

    # GET 请求时显示评价表单
    return render_template('payment/leave_review.html', order=order)

