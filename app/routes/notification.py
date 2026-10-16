# app/routes/notification.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
# 导入所有需要的模型，包括 Goods, Message, Conversation, Order
from app.models import Notification, db, Message, Conversation, Goods, Order # 【修改点1】：新增导入 Order 模型
from sqlalchemy.orm import joinedload # 用于高效加载关联对象

notification_bp = Blueprint('notification', __name__, url_prefix='/notifications')


# 查看消息
@notification_bp.route('/')
@login_required
def index():
    # 获取当前用户的所有通知，按时间倒序
    # 【修改点2】：使用 joinedload 预加载 sender, order 和 order.goods，以减少后续循环中的N+1查询问题
    all_notifications_query = Notification.query.filter_by(recipient_id=current_user.id).order_by(
        Notification.create_time.desc()
    ).options(
        joinedload(Notification.sender), # 确保加载发送者信息
        joinedload(Notification.order).joinedload(Order.goods) # 如果通知类型是关于订单的，预加载订单和商品
    )

    comment_notifications_data = [] # 评论我的
    private_chat_notifications_data = [] # 私信
    order_notifications_data = [] # 【新增】：用于 'order_completed', 'new_review', 'transaction'
    general_notifications_data = [] # 回复我的 (comment_reply) 和其他通用通知

    # 遍历通知，根据类型获取相关联的数据
    for notice in all_notifications_query.all():
        sender_username = "未知用户"
        if notice.sender: # 检查 notice.sender 是否存在，以防 sender_id 为 NULL
            sender_username = notice.sender.username

        notification_info = {
            'id': notice.id,
            'message': notice.message,
            'is_read': notice.is_read,
            'create_time': notice.create_time,
            'sender_username': sender_username,
            'type': notice.type,
            'related_id': notice.related_id
        }

        if notice.type == 'comment':
            # 对于评论通知，我们已经预加载了 goods，可以直接访问
            if notice.related_id: # 确保 related_id 存在
                message_obj = Message.query.options(joinedload(Message.goods)).get(notice.related_id) # 重新查询以确保 Message.goods 加载
                if message_obj and message_obj.goods:
                    notification_info['goods_id'] = message_obj.goods.id
                    notification_info['goods_title'] = message_obj.goods.title
            comment_notifications_data.append(notification_info)
        elif notice.type == 'private_chat':
            # 对于私信通知
            if notice.related_id: # 确保 related_id 存在
                conversation_obj = Conversation.query.options(joinedload(Conversation.goods)).get(notice.related_id)
                if conversation_obj:
                    notification_info['conversation_id'] = conversation_obj.id
                    if conversation_obj.goods:
                        notification_info['goods_title'] = conversation_obj.goods.title
            private_chat_notifications_data.append(notification_info)
        # 【修改点3】：处理新的订单/评价通知类型
        elif notice.type in ['order_completed', 'new_review', 'transaction']:
            # 这里的 notice.order 是通过 joinedload 加载的，可以直接访问
            if notice.order:
                notification_info['order_id'] = notice.order.id
                notification_info['order_no'] = notice.order.order_no
                if notice.order.goods: # order.goods 也已被预加载
                    notification_info['goods_title'] = notice.order.goods.title
            order_notifications_data.append(notification_info)
        else: # 包括 'reply' 和 'comment_reply' 类型，以及其他通用通知
            general_notifications_data.append(notification_info)

    return render_template('notifications.html',
                           comment_notifications=comment_notifications_data,
                           private_chat_notifications=private_chat_notifications_data,
                           general_notifications=general_notifications_data,
                           order_notifications=order_notifications_data) # 【修改点4】：传递新类型的通知

# 标记消息已阅读 (保持不变)
@notification_bp.route('/mark_read/<int:notification_id>')
@login_required
def mark_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.recipient_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return redirect(url_for('notification.index'))

#批量标记已读功能 (保持不变)
@notification_bp.route('/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    """批量标记所有未读消息为已读"""
    try:
        updated_rows = Notification.query.filter_by(
            recipient_id=current_user.id,
            is_read=False
        ).update({Notification.is_read: True})

        db.session.commit()

        if updated_rows > 0:
            flash(f'成功标记 {updated_rows} 条消息为已读')
        else:
            flash('没有未读消息需要标记')

    except Exception as e:
        db.session.rollback()
        flash(f'操作失败: {str(e)}')

    return redirect(url_for('notification.index'))

# 回复留言功能 (保持不变，此路由本身逻辑正确)
@notification_bp.route('/reply/<int:notification_id>', methods=['POST'])
@login_required
def reply(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    if notification.recipient_id != current_user.id:
        flash('没有回复权限')
        return redirect(url_for('notification.index'))

    reply_content = request.form.get('reply_content', '').strip()
    if not reply_content:
        flash('回复内容不能为空')
        return redirect(url_for('notification.index'))

    try:
        original_message = Message.query.get(notification.related_id)
        if not original_message:
            flash('原始留言不存在')
            return redirect(url_for('notification.index'))

        reply_message = Message(
            content=reply_content,
            user_id=current_user.id,
            goods_id=original_message.goods_id,
            parent_id=original_message.id
        )
        db.session.add(reply_message)

        reply_notification = Notification(
            recipient_id=notification.sender_id,
            sender_id=current_user.id,
            message=f"{current_user.username} 回复了你的留言：{reply_content}",
            type='comment_reply',
            related_id=reply_message.id
        )
        db.session.add(reply_notification)

        notification.is_read = True
        db.session.commit()
        flash('回复成功')

    except Exception as e:
        db.session.rollback()
        flash(f'回复失败：{str(e)}')

    return redirect(url_for('goods.goods_detail', goods_id=original_message.goods_id))

