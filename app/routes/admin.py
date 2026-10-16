from os import abort
import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.models import Category, db, Goods, Message, Notification, PrivateMessage, Conversation, MessageLike,GoodsImage,Order,Payment
from flask_login import login_required, current_user
from app.routes.goods import delete_goods
bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.before_request
@login_required
def check_admin():
    if not current_user.is_admin:
        flash('非管理员，禁止访问', 'danger')
        return redirect(url_for('index'))

@bp.route('/')
def admin_home():
    categories = Category.query.all()
    goods = Goods.query.all()
    # 使用正确的字段名 created_at 进行排序
    messages = Message.query.order_by(Message.created_at.desc()).limit(5).all()
    return render_template('admin.html',
                         categories=categories,
                         goods=goods,
                         messages=messages)

# 分类操作
@bp.route('/category/add', methods=['POST'])
def add_category():
    name = request.form.get('name', '').strip()
    if not name:
        flash('分类名称不能为空', 'danger')
    else:
        category = Category(name=name)
        db.session.add(category)
        db.session.commit()
        flash('分类添加成功', 'success')
    return redirect(url_for('admin.admin_home'))


@bp.route('/category/delete/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    try:
        # 获取该分类下所有商品
        goods_list = Goods.query.filter_by(category_id=category_id).all()

        # 先删除所有关联消息
        from app.models import Message
        for goods in goods_list:
            Message.query.filter_by(goods_id=goods.id).delete()

        # 然后删除所有商品
        Goods.query.filter_by(category_id=category_id).delete()

        # 最后删除分类
        Category.query.filter_by(id=category_id).delete()

        db.session.commit()
        flash('分类及关联数据已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
        # 记录完整错误日志
        current_app.logger.error(f"删除分类失败: {str(e)}", exc_info=True)
    return redirect(url_for('admin.admin_home'))


@bp.route('/goods/delete/<int:goods_id>', methods=['POST'])
def delete_goods(goods_id):
    goods = Goods.query.options(db.joinedload(Goods.images)).get_or_404(goods_id)

    # 【修改点2-2：新增：删除关联的订单和支付记录】
    # 1. 查询所有与该商品相关的订单
    orders_to_delete = Order.query.filter_by(goods_id=goods_id).all()
    for order in orders_to_delete:
        # 2. 删除与这些订单相关的支付记录
        Payment.query.filter_by(order_id=order.id).delete(synchronize_session=False)
        # 3. 将订单标记为删除
        db.session.delete(order)

    # --- 开始修改部分：处理留言、私信和通知的彻底删除 ---

    # 预先收集所有相关的留言ID和会话ID，因为后续删除操作会清空这些数据
    # 先获取所有与商品相关的留言ID (包括父留言和子回复)
    all_messages_for_goods = Message.query.filter_by(goods_id=goods_id).all()
    all_message_ids_to_delete = [msg.id for msg in all_messages_for_goods]

    # 先获取所有与商品相关的会话ID (包括 PrivateMessage)
    all_conversations_for_goods = Conversation.query.filter_by(goods_id=goods_id).all()
    all_conversation_ids_to_delete = [conv.id for conv in all_conversations_for_goods]

    # 定义一个辅助函数，用于递归删除留言、其点赞和相关通知
    def delete_message_recursive(message_obj):
        # 删除当前留言/回复的所有点赞
        MessageLike.query.filter_by(message_id=message_obj.id).delete(synchronize_session=False)

        # 递归删除所有子回复
        # 注意：遍历list(message_obj.replies)的拷贝，避免在迭代时修改集合
        for reply in list(message_obj.replies):
            delete_message_recursive(reply)
            # 在递归调用中删除子回复对象
            db.session.delete(reply)

        # 最后删除留言本身
        db.session.delete(message_obj)

    # 留言+点赞：遍历所有顶级留言，并递归删除它们及其所有回复、点赞
    top_level_messages = Message.query.filter_by(goods_id=goods_id, parent_id=None).all()
    for msg in top_level_messages:
        delete_message_recursive(msg)

    # 会话+私信：遍历所有相关会话，并删除其所有私信
    for conversation in all_conversations_for_goods:  # 使用预先获取的列表
        PrivateMessage.query.filter_by(conversation_id=conversation.id).delete(synchronize_session=False)
        db.session.delete(conversation)

    # 收藏
    goods.favorited_by = []  # 清空多对多关系

    # 通知 (现在使用预先收集的ID进行删除，确保全面性)
    # 删除直接与商品相关的通知 (如果 type='goods' 且 related_id 是 goods_id)
    Notification.query.filter_by(related_id=goods_id, type='goods').delete(synchronize_session=False)

    # 删除与已删除留言相关的通知 (包括评论和回复类型)
    if all_message_ids_to_delete:
        Notification.query.filter(Notification.type.in_(['comment', 'reply', 'comment_reply']),  # 增加 'comment_reply' 类型
                                  Notification.related_id.in_(all_message_ids_to_delete)).delete(
            synchronize_session=False)

    # 删除与已删除私聊会话相关的通知
    if all_conversation_ids_to_delete:
        Notification.query.filter(Notification.type == 'private_chat',
                                  Notification.related_id.in_(all_conversation_ids_to_delete)).delete(
            synchronize_session=False)

    # --- 结束修改部分 ---

    goods_image_folder = os.path.join(current_app.config['GOODS_FOLDER'], str(goods_id))
    if os.path.exists(goods_image_folder):
        shutil.rmtree(goods_image_folder)
        current_app.logger.info(f"Deleted goods image folder by admin: {goods_image_folder}")

    # Goods (GoodsImage records会因为 cascade 自动删除)
    db.session.delete(goods)

    # 提交事务
    try:
        db.session.commit()
        flash('商品及相关数据已成功删除', 'success')
    except Exception as e:
        db.session.rollback()  # 出错时回滚
        flash(f'删除失败：{str(e)}', 'danger')
        current_app.logger.error(f"管理员删除商品失败: {str(e)}", exc_info=True)

    return redirect(url_for('admin.admin_home'))


@bp.route('/message/delete/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    try:
        message = Message.query.get_or_404(message_id)
        db.session.delete(message)
        db.session.commit()
        flash('留言删除成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'留言删除失败: {str(e)}', 'danger')
        current_app.logger.error(f"删除留言失败: {str(e)}", exc_info=True)
    return redirect(url_for('admin.admin_home'))