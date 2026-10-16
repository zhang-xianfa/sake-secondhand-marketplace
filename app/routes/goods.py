# app/routes/goods.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, jsonify
from flask_login import login_required, current_user
from app.models import Goods, db, Category, Message, Notification, MessageLike,Conversation,PrivateMessage,GoodsImage,Order,Review,Payment
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from app import socketio # 导入 socketio 对象
import uuid
import shutil

bp = Blueprint('goods', __name__, url_prefix='/goods')


# 新增辅助函数
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@bp.route('/publish', methods=['GET', 'POST'])
@login_required
def publish():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        condition = request.form['condition']
        category_id = request.form['category_id']
        # image_url = request.form['image_url']
        files = request.files.getlist('image_files')

        if not files or all(f.filename == '' for f in files):
            flash('请至少选择一张图片文件', 'danger')
            return redirect(url_for('goods.publish'))

        # image_url = None

        # # file = request.files['image_file']
        # if 'image_file' not in request.files or file.filename == "":
        #     flash('没有选择图片文件', 'danger')
        #     return redirect(url_for('goods.publish'))
        #
        # if file and allowed_file(file.filename):
        #     upload_folder_path = os.path.join(current_app.static_folder, 'uploads', 'goods_images')
        #     os.makedirs(upload_folder_path, exist_ok=True)
        #     filename = secure_filename(file.filename)
        #     file_path = os.path.join(upload_folder_path, filename)
        #     file.save(file_path)
        #     image_url = url_for('static', filename=f'uploads/goods_images/{filename}')
        # else:
        #     flash('上传文件格式不支持，请上传 JPG, PNG, 或 GIF 格式的图片。', 'danger')
        #     return redirect(url_for('goods.publish'))

        goods = Goods(
            title=title,
            description=description,
            price=price,
            condition=condition,
            # image_url=image_url,
            seller_id=current_user.id,
            category_id=category_id,
            create_time=datetime.utcnow()
        )
        db.session.add(goods)
        db.session.flush()
        uploaded_image_urls = []
        for i, file in enumerate(files):
            if file and allowed_file(file.filename):
                # 【为每个商品创建独立的图片存储子文件夹】
                # 例如：static/uploads/goods_images/{goods_id}/
                goods_upload_folder = os.path.join(current_app.config['GOODS_FOLDER'], str(goods.id))
                os.makedirs(goods_upload_folder, exist_ok=True)

                # 【使用UUID生成唯一文件名，防止重名】
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4()}.{ext}"
                file_path = os.path.join(goods_upload_folder, unique_filename)
                file.save(file_path)
                # 构造图片的可访问URL
                image_url = url_for('static', filename=f'uploads/goods_images/{goods.id}/{unique_filename}')
                uploaded_image_urls.append(image_url)

                goods_image = GoodsImage(
                    goods_id=goods.id,
                    image_url=image_url,
                    order=i  # 记录上传顺序，可用于展示排序
                )
                db.session.add(goods_image)
            else:
                flash(f'文件 {file.filename} 格式不支持或为空，已跳过。', 'warning')

        if not uploaded_image_urls:
            # 如果没有有效图片上传，回滚商品创建
            db.session.rollback()
            flash('没有有效的图片文件上传，商品发布失败。', 'danger')
            return redirect(url_for('goods.publish'))

        try:
            db.session.commit()
            flash('物品发布成功！')
            return redirect(url_for('index.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'商品发布失败: {str(e)}', 'danger')
            current_app.logger.error(f"商品发布失败: {str(e)}", exc_info=True)
            return redirect(url_for('goods.publish'))
    categories = Category.query.all()
    return render_template('publish.html', categories=categories)


# 商品详情⻚
# app/routes/goods.py (修改goods_detail路由)
@bp.route('/<int:goods_id>')
def goods_detail(goods_id):
    page = request.args.get('page', 1, type=int)
    # goods = Goods.query.get_or_404(goods_id)
    # 【使用 joinedload 预加载 goods.images 和 message.user】
    goods = Goods.query.options(
        db.joinedload(Goods.images),
        db.joinedload(Goods.seller).joinedload(Review.reviews_received)  # 【新增】：加载卖家的评价信息
    ).get_or_404(goods_id)

    # 查询一级评论（无父评论的留言）
    parent_messages = Message.query.filter_by(
        goods_id=goods_id,
        parent_id=None  # 只获取一级评论
    ).order_by(Message.created_at.desc()).paginate(page=page, per_page=5)

    return render_template('goods_detail.html', goods=goods, parent_messages=parent_messages)


# 留⾔功能
@bp.route('/<int:goods_id>/message', methods=['POST'])
@login_required
def leave_message(goods_id):
    content = request.form.get('content', '').strip()
    if not content:
        flash('留言内容不能为空')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))

    goods = Goods.query.get_or_404(goods_id)

    # 调试：打印关键信息，确认数据是否正确
    print(f"留言者ID：{current_user.id}，卖家ID：{goods.seller_id}")
    print(f"准备创建通知：接收者={goods.seller_id}，发送者={current_user.id}，内容={content}")

    # 创建留言
    new_message = Message(
        content=content,
        user_id=current_user.id,
        goods_id=goods_id
    )
    db.session.add(new_message)
    db.session.flush() # 确保 new_message.id 可用

    # 创建通知，并指定类型和关联ID
    notification_msg_content = f"{current_user.username} 在《{goods.title}》下留言：{content}"
    notification = Notification(
        recipient_id=goods.seller_id,  # 接收者是卖家
        sender_id=current_user.id,  # 发送者是当前用户
        message=notification_msg_content,
        type='comment', # 明确类型为留言
        related_id=new_message.id # 关联到留言ID
    )
    db.session.add(notification)

    # 提交时捕获可能的错误
    try:
        db.session.commit()
        print("通知已成功保存到数据库！")  # 调试：确认提交成功
        flash('留言成功！卖家已收到通知。')

        # 使用 WebSocket 实时通知卖家
        # 使用 str() 转换 ID，因为 SocketIO room 接受字符串
        socketio.emit(
            'new_notification',
            {
                'type': 'comment',
                'message': notification_msg_content,
                'sender_username': current_user.username,
                'url': url_for('goods.goods_detail', goods_id=goods.id, _external=True) + '#comment_section' # 可以定位到留言区
            },
            room=str(goods.seller_id)
        )

    except Exception as e:
        db.session.rollback()  # 提交失败时回滚
        print(f"保存通知失败：{str(e)}")  # 打印错误原因
        flash('留言失败，请稍后再试')

    return redirect(url_for('goods.goods_detail', goods_id=goods_id))


@bp.route('/edit/<int:goods_id>', methods=['GET', 'POST'])
@login_required
def edit_goods(goods_id):
    goods = Goods.query.get_or_404(goods_id)
    if goods.seller_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        goods.title = request.form['title']
        goods.description = request.form['description']
        goods.price = request.form['price']
        goods.condition = request.form['condition']
        # !!!暂时不可更改上传的图片，后续优化
        # goods.image_url = request.form['image_url']
        goods.category_id = request.form['category_id']
        db.session.commit()
        flash('商品更新成功')
        return redirect(url_for('goods.goods_detail', goods_id=goods.id))

    categories = Category.query.all()
    return render_template('edit_goods.html', goods=goods, categories=categories)


@bp.route('/delete/<int:goods_id>', methods=['POST'])
@login_required
def delete_goods(goods_id):
    goods = Goods.query.options(db.joinedload(Goods.images)).get_or_404(goods_id)
    if goods.seller_id != current_user.id:
        abort(403)

    # 【修改点1-2：新增：删除关联的订单和支付记录】
    # 1. 查询所有与该商品相关的订单
    orders_to_delete = Order.query.filter_by(goods_id=goods_id).all()
    for order in orders_to_delete:
        # 2. 删除与这些订单相关的支付记录
        Payment.query.filter_by(order_id=order.id).delete(synchronize_session=False)
        # 3. 将订单标记为删除
        db.session.delete(order)

    # --- 开始修改部分：处理留言、私信和通知的彻底删除 ---

    # 预先收集所有相关的留言ID和会话ID，因为后续删除操作会清空这些数据
    all_messages_for_goods = Message.query.filter_by(goods_id=goods_id).all()
    all_message_ids_to_delete = [msg.id for msg in all_messages_for_goods]

    all_conversations_for_goods = Conversation.query.filter_by(goods_id=goods_id).all()
    all_conversation_ids_to_delete = [conv.id for conv in all_conversations_for_goods]

    # 定义一个辅助函数，用于递归删除留言、其点赞和相关通知
    def delete_message_recursive(message_obj):
        # 删除当前留言/回复的所有点赞
        MessageLike.query.filter_by(message_id=message_obj.id).delete(synchronize_session=False)

        # 递归删除所有子回复
        for reply in list(message_obj.replies):  # 遍历拷贝，避免修改集合问题
            delete_message_recursive(reply)
            db.session.delete(reply)  # 删除子回复对象

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
    goods.favorited_by = []  # 清空多对多关系，移除在 favorites 表中的关联

    # 通知 (现在使用预先收集的ID进行删除，确保全面性)
    Notification.query.filter_by(related_id=goods_id, type='goods').delete(synchronize_session=False)

    if all_message_ids_to_delete:
        Notification.query.filter(Notification.type.in_(['comment', 'reply', 'comment_reply']),  # 增加 'comment_reply' 类型
                                  Notification.related_id.in_(all_message_ids_to_delete)).delete(
            synchronize_session=False)
    if all_conversation_ids_to_delete:
        Notification.query.filter(Notification.type == 'private_chat',
                                  Notification.related_id.in_(all_conversation_ids_to_delete)).delete(
            synchronize_session=False)

    # --- 结束修改部分 ---

    # 删除关联的图片文件 (递归删除整个商品图片文件夹)
    goods_image_folder = os.path.join(current_app.config['GOODS_FOLDER'], str(goods_id))
    if os.path.exists(goods_image_folder):
        shutil.rmtree(goods_image_folder)
        current_app.logger.info(f"Deleted goods image folder: {goods_image_folder}")

    # 商品 (GoodsImage 记录会因为 Goods 模型上的 cascade="all, delete-orphan" 而自动删除)
    db.session.delete(goods)

    # 提交所有事务
    try:
        db.session.commit()
        flash('商品及相关数据已成功删除', 'success')
    except Exception as e:
        db.session.rollback()  # 提交失败时回滚所有操作
        flash(f'删除失败：{str(e)}', 'danger')
        current_app.logger.error(f"删除商品失败: {str(e)}", exc_info=True)

    return redirect(url_for('user_center.dashboard'))

# 收藏
@bp.route('/favorite/<int:goods_id>')
@login_required
def favorite(goods_id):
    goods = Goods.query.get_or_404(goods_id)
    if goods not in current_user.favorites:
        current_user.favorites.append(goods)
        db.session.commit()
        flash('已收藏')
        return redirect(request.referrer or url_for('index.index'))



# 取消收藏
@bp.route('/unfavorite/<int:goods_id>')
@login_required
def unfavorite(goods_id):
    goods = Goods.query.get_or_404(goods_id)
    if goods in current_user.favorites:
        current_user.favorites.remove(goods)
        db.session.commit()
        flash('已取消收藏')
        return redirect(request.referrer or url_for('index.index'))


# 商品上架、下架开关
@bp.route('/<int:goods_id>/toggle_status')
@login_required
def toggle_goods_status(goods_id):
    # if not current_user.is_admin:
    #     abort(403)
    goods = Goods.query.get_or_404(goods_id)
    goods.is_sold = not goods.is_sold
    db.session.commit()
    flash(f'商品「{goods.title}」已{"下架" if goods.is_sold else "上架"}')
    return redirect(url_for('user_center.dashboard'))


# 在文件末尾添加
@bp.route('/message/like/<int:message_id>', methods=['POST'])
@login_required
def like_message(message_id):
    message = Message.query.get_or_404(message_id)

    # 检查是否已经点赞
    existing_like = MessageLike.query.filter_by(
        message_id=message_id,
        user_id=current_user.id
    ).first()

    if existing_like:
        # 取消点赞
        db.session.delete(existing_like)
        action = 'unliked'
    else:
        # 添加点赞
        new_like = MessageLike(
            message_id=message_id,
            user_id=current_user.id
        )
        db.session.add(new_like)
        action = 'liked'

    try:
        db.session.commit()
        # 返回点赞数和操作结果
        return {
            'status': 'success',
            'action': action,
            'like_count': message.likes.count()
        }
    except Exception as e:
        db.session.rollback()
        return {'status': 'error', 'message': str(e)}, 500


# 在like_message路由下方添加
@bp.route('/reply/like/<int:reply_id>', methods=['POST'])
@login_required
def like_reply(reply_id):
    """处理对回复的点赞/取消点赞"""
    # 复用已有的消息点赞逻辑，因为回复也是Message模型
    reply = Message.query.get_or_404(reply_id)

    # 检查是否已经点赞
    existing_like = MessageLike.query.filter_by(
        message_id=reply_id,
        user_id=current_user.id
    ).first()

    if existing_like:
        # 取消点赞
        db.session.delete(existing_like)
        action = 'unliked'
    else:
        # 添加点赞
        new_like = MessageLike(
            message_id=reply_id,
            user_id=current_user.id
        )
        db.session.add(new_like)
        action = 'liked'

    try:
        db.session.commit()
        # 返回点赞数和操作结果
        return {
            'status': 'success',
            'action': action,
            'like_count': reply.likes.count()
        }
    except Exception as e:
        db.session.rollback()
        return {'status': 'error', 'message': str(e)}, 500

# 回复留言功能
@bp.route('/<int:goods_id>/reply/<int:message_id>', methods=['POST'])
@login_required
def reply_to_message(goods_id, message_id):
    """处理对留言的回复"""
    content = request.form.get('content', '').strip()
    if not content:
        flash('回复内容不能为空', 'error')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))

    # 获取被回复的原留言
    parent_message = Message.query.get_or_404(message_id)

    # 创建回复留言（设置parent_id关联到原留言）
    reply = Message(
        content=content,
        goods_id=goods_id,
        user_id=current_user.id,
        parent_id=message_id
    )
    db.session.add(reply)
    db.session.flush()  # 确保reply.id可用

    # 获取商品信息，用于通知
    goods = Goods.query.get_or_404(goods_id)

    # 创建通知：通知被回复的用户
    notification_content = f"{current_user.username} 回复了你的留言：{content}"
    notification = Notification(
        recipient_id=parent_message.user_id,  # 被回复者接收通知
        sender_id=current_user.id,
        message=notification_content,
        type='reply',  # 类型为回复
        related_id=reply.id
    )
    db.session.add(notification)

    try:
        db.session.commit()
        flash('回复成功', 'success')

        # 发送WebSocket实时通知
        socketio.emit(
            'new_notification',
            {
                'type': 'reply',
                'message': notification_content,
                'sender_username': current_user.username,
                'url': url_for('goods.goods_detail', goods_id=goods_id, _external=True) + '#comment_section'
            },
            room=str(parent_message.user_id)  # 发送到被回复者的房间
        )
    except Exception as e:
        db.session.rollback()
        flash(f'回复失败：{str(e)}', 'error')

    return redirect(url_for('goods.goods_detail', goods_id=goods_id))


@bp.route('/message/delete/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    """删除留言，先删除关联的点赞记录和通知"""
    message = Message.query.get_or_404(message_id)

    # 验证权限：只有留言作者可以删除
    if message.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': '没有删除权限'}), 403

    try:
        # 先删除所有关联的点赞记录和通知
        from app.models import MessageLike, Notification  # 导入点赞模型和Notification

        # 递归删除辅助函数：删除当前留言/回复、其点赞和相关通知
        def delete_message_recursive(msg_obj):
            # 删除当前留言/回复的所有点赞
            MessageLike.query.filter_by(message_id=msg_obj.id).delete(synchronize_session=False)

            # 删除与当前留言/回复相关的通知
            Notification.query.filter(
                (Notification.type.in_(['comment', 'reply', 'comment_reply'])) & (Notification.related_id == msg_obj.id)
            ).delete(synchronize_session=False)

            # 递归处理子回复
            # 使用list()拷贝，避免在迭代时修改集合
            for sub_reply in list(msg_obj.replies):
                delete_message_recursive(sub_reply)
                db.session.delete(sub_reply)  # 删除子回复对象

        # 调用递归函数处理主留言（及其所有子回复）
        delete_message_recursive(message)

        # 最后删除主留言本身
        db.session.delete(message)  # 修复笔误：db.session.session.delete -> db.session.delete
        db.session.commit()
        return jsonify({'status': 'success', 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除留言失败: {str(e)}", exc_info=True)  # 添加日志记录
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/reply/delete/<int:reply_id>', methods=['POST'])
@login_required
def delete_reply(reply_id):
    """删除回复，先删除关联的点赞记录和通知"""
    reply = Message.query.get_or_404(reply_id)

    # 验证权限：只有回复作者可以删除
    if reply.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': '没有删除权限'}), 403

    try:
        from app.models import MessageLike, Notification # 导入点赞模型和Notification

        # 递归删除辅助函数：删除当前留言/回复、其点赞和相关通知
        def delete_message_recursive(msg_obj):
            # 删除当前留言/回复的所有点赞
            MessageLike.query.filter_by(message_id=msg_obj.id).delete(synchronize_session=False)

            # 删除与当前留言/回复相关的通知
            Notification.query.filter(
                (Notification.type.in_(['comment', 'reply', 'comment_reply'])) & (Notification.related_id == msg_obj.id)
            ).delete(synchronize_session=False)

            # 递归处理子回复
            for sub_reply in list(msg_obj.replies): # 遍历拷贝，避免修改集合问题
                delete_message_recursive(sub_reply)
                db.session.delete(sub_reply) # 删除子回复对象

        # 调用递归函数处理当前回复（及其所有子回复）
        delete_message_recursive(reply)

        # 最后删除当前回复本身
        db.session.delete(reply)
        db.session.commit()

        return jsonify({'status': 'success', 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除回复失败: {str(e)}", exc_info=True) # 添加日志记录
        return jsonify({'status': 'error', 'message': str(e)}), 500



# 在文件末尾添加
@bp.route('/<int:goods_id>/transaction', methods=['GET', 'POST'])
@login_required
def transaction(goods_id):
    goods = Goods.query.get_or_404(goods_id)

    # 不能购买自己的商品
    if goods.seller_id == current_user.id:
        flash('不能购买自己发布的商品', 'danger')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))

    # 不能购买已售出的商品
    if goods.is_sold:
        flash('该商品已售出', 'danger')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))

    if request.method == 'POST':
        # 处理交易提交逻辑
        # 这里可以添加交易记录创建等逻辑
        flash('交易请求已发送，请等待卖家确认', 'success')
        return redirect(url_for('goods.goods_detail', goods_id=goods_id))

    return render_template('transaction.html', goods=goods)