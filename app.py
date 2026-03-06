import os
import pyodbc
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'campus_trading_2026_secure_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'


# --- 数据库配置 (使用通用驱动解决权限与版本问题) ---
def get_db_conn():
    try:
        conn_str = (
            "DRIVER={SQL Server};"  # 通用驱动名
            "SERVER=LAPTOP-SQPCLBP7\\MSSQLSERVER01;"
            "DATABASE=CampusMarketDB;"
            "UID=sa;"
            "PWD=123456;"
            "TrustServerCertificate=yes;"
        )
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None


def query_db(query, args=(), one=False):
    conn = get_db_conn()
    if not conn: return None
    cursor = conn.cursor()
    cursor.execute(query, args)
    if cursor.description is None: return None
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return (results[0] if results else None) if one else results


# --- 路由逻辑 ---

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = query_db("SELECT * FROM Users WHERE Username=? AND Password=?", (username, password), one=True)
        if user:
            session['user_id'] = user['UserID']
            session['username'] = user['Username']
            return redirect(url_for('index'))
        flash("用户名或密码错误")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO Users (Username, Password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("注册成功")
            return redirect(url_for('login'))
        except:
            flash("用户名已存在")
        finally:
            conn.close()
    return render_template('register.html')


# 核心修正：对应 index.html 中的 post_item
@app.route('/publish', methods=['GET', 'POST'])
def post_item():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        f = request.files.get('image')
        filename = secure_filename(f.filename) if f and f.filename != '' else "default.png"
        if f and f.filename != '':
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Items (Title, Category, SellerID, Price, Condition, Description, ImagePath, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'available')
        """, (request.form['title'], request.form['category'], session['user_id'],
              request.form['price'], request.form['condition'],
              request.form['description'], filename))
        conn.commit()
        conn.close()
        return redirect(url_for('categories'))
    return render_template('publish.html', username=session['username'])


@app.route('/categories')
def categories():
    if 'user_id' not in session: return redirect(url_for('login'))
    cat = request.args.get('type')
    if cat:
        items = query_db("SELECT * FROM Items WHERE Category = ? AND Status = 'available'", (cat,))
    else:
        items = query_db("SELECT * FROM Items WHERE Status = 'available'")
    return render_template('finding-product.html', items=items, username=session['username'])


@app.route('/profile')
def profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    my_items = query_db("SELECT * FROM Items WHERE SellerID = ?", (session['user_id'],))
    return render_template('profile.html', my_items=my_items, username=session['username'])


@app.route('/change_password', methods=['POST'])
def change_password():
    new_pwd = request.form.get('new_password')
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET Password = ? WHERE UserID = ?", (new_pwd, session['user_id']))
    conn.commit()
    conn.close()
    flash("密码已更新")
    return redirect(url_for('profile'))


@app.route('/messages')
def messages():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('messages.html', username=session['username'], contacts=[])


@app.route('/my_orders')
def my_orders():
    return "<h1>订单中心</h1><p>开发中...</p><a href='/'>返回</a>"


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
