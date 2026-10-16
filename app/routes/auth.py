from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import db, User
from flask_login import login_user, logout_user, login_required, LoginManager, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# 在定义blueprint的时候，如果没给blueprint设置name，
# url_for的endpoint默认是：蓝图名称.视图函数名# 如果我们在auth blueprint是这样定义的：auth_bp = Blueprint('auth', __name__)
# 后⾯应该url_for('auth.login')
# 之后重定向时代码应该是：return redirect(url_for('auth.login'))
bp = Blueprint('auth', __name__)


# 注册⻚⾯
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        student_id = request.form.get('student_id')
        department = request.form.get('department')
        email = request.form.get('email')
        phone = request.form.get('phone')
        avatar = request.form.get('avatar')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('⽤户名已存在')
            return redirect(url_for('auth_bp.register'))

        hashed_password = generate_password_hash(password)
        user = User(
            username=username,
            password=hashed_password,
            student_id=student_id,
            department=department,
            email=email,
            phone=phone,
            avatar=avatar
        )
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录')
        return redirect(url_for('auth.login'))
    return render_template('register.html')


# 登录⻚⾯
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('登录成功')

            # 获取next参数，如果不存在则跳转到首页
            next_page = request.form.get('next') or request.args.get('next')

            return redirect(url_for('index.index'))
        else:
            flash('⽤户名或密码错误')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


# 退出登录
@ bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录')
    return redirect(url_for('index.index'))