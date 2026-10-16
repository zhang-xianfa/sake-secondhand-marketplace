from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from pymysql.converters import conversions

from app import socketio
from app.models import db, Conversation, PrivateMessage, User, Goods, Notification
from sqlalchemy import or_, and_
from datetime import datetime

bp = Blueprint('chat',__name__,url_prefix='/chat')

# 私信列表页
@bp.route('/')
@login_required
def chat_list():
    conversation = Conversation.query.filter(
        or_(Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id)
    ).order_by(Conversation.last_message_at.desc()).all()
    return render_template('chat_list.html',conversations=conversation)
# 聊天室
@bp.route('/<int:conversation_id>')
@login_required
def chat_room(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if current_user.id not in [conversation.user1_id, conversation.user2_id]:
        flash('您无权访问此对话。','danger')
        return redirect(url_for('chat.chat_list'))

    PrivateMessage.query.filter(
        PrivateMessage.conversation_id == conversation_id,
        PrivateMessage.sender_id != current_user.id,
        PrivateMessage.is_read == False
    ).update({'is_read': True})

    db.session.commit()
    messages = PrivateMessage.query.filter_by(conversation_id=conversation_id).order_by(PrivateMessage.timestamp).all()
    other_user = conversation.user1 if conversation.user2_id == current_user.id else conversation.user2
    return render_template('chat_room.html',conversation=conversation,messages=messages,other_user=other_user)
# 发送私信
@bp.route('/<int:conversation_id>/send',methods=['GET','POST'])
@login_required
def send_message(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if current_user.id not in [conversation.user1_id, conversation.user2_id]:
        flash('您无权发送消息到此对话。', 'danger')
        return redirect(url_for('chat.chat_list'))
    content = request.form.get('content','').strip()
    if not content:
        flash('消息内容不得为空', 'warning')
        return redirect(url_for('chat.chat_room',conversation_id=conversation.id))
    new_message = PrivateMessage(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=content,
    )
    db.session.add(new_message)
    db.session.flush()
    conversation.last_message_at = datetime.utcnow()
    recipient_id = conversation.user1_id if conversation.user2_id == current_user.id else conversation.user2_id
    notification_message = f"您收到来自 {current_user.username} 的新私信: {content[:50]}..."
    notification = Notification(
        recipient_id=recipient_id,
        sender_id=current_user.id,
        message=notification_message,
        type='private_chat',
        related_id=conversation.id
    )
    db.session.add(notification)


    try:
        db.session.commit()
        flash('消息发送成功。', 'success')
        socketio.emit(
            'new_notification',
            {
                'type': 'private_chat',
                'message': notification_message,
                'sender_username': current_user.username,
                'url': url_for('chat.chat_room', conversation_id=conversation.id, _external=True)
            },
            room=str(recipient_id)
        )

        socketio.emit(
            'new_private_message',
            {
                'sender_id': current_user.id,
                'sender_username': current_user.username,
                'content': content,
                'timestamp': new_message.timestamp.strftime('%Y-%m-%d %H:%M'),
                'conversation_id': conversation.id
            },
            room=str(conversation.user1_id)  # 通知 user1
        )
        if conversation.user1_id != conversation.user2_id:
            socketio.emit(
                'new_private_message',
                {
                    'sender_id': current_user.id,
                    'sender_username': current_user.username,
                    'content': content,
                    'timestamp': new_message.timestamp.strftime('%Y-%m-%d %H:%M'),
                    'conversation_id': conversation.id
                },
                room=str(conversation.user2_id)  # 通知 user2
            )

    except Exception as e:
        db.session.rollback()
        flash(f'消息发送失败: {e}', 'danger')

    return redirect(url_for('chat.chat_room', conversation_id=conversation_id))

# 发起私聊
@bp.route('/initiate/<int:goods_id>', methods=['POST'])
@login_required
def initiate_chat(goods_id):
    goods = Goods.query.get_or_404(goods_id)
    seller = goods.seller

    # 避免用户与自己聊天
    if current_user.id == seller.id:
        flash('您不能与自己聊天。', 'warning')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))

    # 检查是否已存在当前用户与该卖家关于此商品的会话
    conversation = Conversation.query.filter(
        or_(
            and_(Conversation.user1_id == current_user.id, Conversation.user2_id == seller.id,
                 Conversation.goods_id == goods_id),
            and_(Conversation.user1_id == seller.id, Conversation.user2_id == current_user.id,
                 Conversation.goods_id == goods_id)
        )
    ).first()

    if not conversation:
        # 如果不存在，则创建新的会话
        conversation = Conversation(
            user1_id=current_user.id,
            user2_id=seller.id,
            goods_id=goods_id  # 关联到特定商品
        )
        db.session.add(conversation)
        try:
            db.session.commit()
            flash('已创建新对话。', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'创建对话失败: {e}', 'danger')
            return redirect(url_for('goods.goods_detail', goods_id=goods_id))
    else:
        flash('您已与卖家有此商品的对话。', 'info')

    return redirect(url_for('chat.chat_room', conversation_id=conversation.id))




