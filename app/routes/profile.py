import os
from flask import current_app, request, flash, url_for, redirect, render_template, Blueprint
from flask_login import login_required, current_user
from app import db
from app.models import User

bp = Blueprint('profile', __name__)


# ⼯具函数检查⽂件
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


@bp.route('/')  # 对应 URL: /profile/
def index():  # 端点名称为 profile.index（蓝图名.函数名）
    user = User.query.get(current_user.id)
    return render_template('profile/profile.html', user=user)


from werkzeug.utils import secure_filename


@bp.route('/profile/avatars', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        file = request.files.get('avatar')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            avatar_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(avatar_path)

            # 存⼊数据库相对路径
            current_user.avatar = f'/static/uploads/avatars/{filename}'
            db.session.commit()
            flash('头像上传成功')
            return redirect(url_for('profile.profile'))
        else:
            flash('请上传正确的图⽚格式')
    return render_template('upload_avatar.html')


@bp.route('/edit', methods=['GET', 'POST'])
@login_required  # 确保用户已登录
def edit_profile():
    # GET请求：渲染修改信息页面，传递当前用户给模板
    if request.method == 'GET':
        return render_template('edit_profile.html', user=current_user)

    # POST请求：处理表单提交
    if request.method == 'POST':
        # 获取表单数据
        new_username = request.form.get('username', '').strip()
        new_email = request.form.get('email', '').strip()
        new_phone = request.form.get('phone', '').strip()  # 新增电话字段处理
        new_department = request.form.get('department', '').strip()  # 新增院系字段

        # 数据验证
        if not new_username:
            flash('用户名不能为空', 'danger')
            return redirect(url_for('profile.edit_profile'))

        # 检查用户名是否已被占用（排除当前用户）
        existing_user = User.query.filter(
            User.username == new_username,
            User.id != current_user.id
        ).first()
        if existing_user:
            flash('用户名已被占用', 'danger')
            return redirect(url_for('profile.edit_profile'))

        # 邮箱格式验证（简单验证）
        if new_email and '@' not in new_email:
            flash('请输入有效的邮箱地址', 'danger')
            return redirect(url_for('profile.edit_profile'))

        # 更新用户信息
        current_user.username = new_username
        current_user.email = new_email
        current_user.phone = new_phone  # 保存电话
        current_user.department = new_department  # 保存院系

        try:
            db.session.commit()
            flash('信息修改成功', 'success')
            return redirect(url_for('profile.index'))  # 建议返回个人主页
        except Exception as e:
            db.session.rollback()
            flash(f'修改失败：{str(e)}', 'danger')
            return redirect(url_for('profile.edit_profile'))  # 修正端点引用，添加蓝图前缀