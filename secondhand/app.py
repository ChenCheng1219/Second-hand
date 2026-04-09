import os
import pyodbc
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)
app.secret_key = 'campus_trading_2026_secure_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# 教室字典（全局定义）
CAMPUS_ROOMS = {
    '2楼 (2nd Floor)': ['215', '223', '230', 'JUPITER', 'VEGA', 'Library'],
    '1楼 (1st Floor)': ['123', '124', '126', '156', 'Restaurant', 'Cafe'],
    '0楼 (Ground Floor)': ['004', '007', '014', '033', '085', '091', 'Archive']
}


# --- 数据库配置 ---
def get_db_conn():
    """获取数据库连接"""
    try:
        conn_str = (
            "DRIVER={SQL Server};"
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
    """查询数据库并返回字典列表"""
    conn = get_db_conn()
    if not conn:
        return None if one else []
    cursor = conn.cursor()
    try:
        cursor.execute(query, args)
        if cursor.description is None:
            return None if one else []

        columns = [column[0].lower() for column in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return (results[0] if results else None) if one else results
    except Exception as e:
        print(f"查询失败: {e}")
        return None if one else []
    finally:
        conn.close()


def execute_db(query, args=()):
    """执行数据库修改操作"""
    conn = get_db_conn()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(query, args)
        conn.commit()
        return True
    except Exception as e:
        print(f"数据库错误: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_floor_image(location):
    """根据地点返回对应的楼层地图图片名"""
    if not location:
        return None
    loc = str(location).upper()

    # 数字识别
    room_match = re.search(r'(\d{3})', loc)
    if room_match:
        first_digit = room_match.group(1)[0]
        if first_digit == '2':
            return 'floor_2.png'
        if first_digit == '1':
            return 'floor_1.png'
        if first_digit == '0':
            return 'floor_0.png'

    # 特殊名称识别
    if any(x in loc for x in ['JUPITER', 'VEGA', 'LIBRARY']):
        return 'floor_2.png'
    if any(x in loc for x in ['RESTAURANT', 'CAFE', 'INFO']):
        return 'floor_1.png'
    if any(x in loc for x in ['LAB', 'ARCHIVE']):
        return 'floor_0.png'

    return None


# --- 路由逻辑 ---

@app.route('/')
def index():
    """首页"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = query_db("SELECT * FROM Users WHERE Username=? AND Password=?",
                        (username, password), one=True)

        if user:
            session['user_id'] = user['userid']
            session['username'] = user['username']
            return redirect(url_for('index'))

        flash("用户名或密码错误")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 检查用户名是否已存在
        existing = query_db("SELECT UserID FROM Users WHERE Username=?", (username,), one=True)
        if existing:
            flash("用户名已存在")
            return redirect(url_for('register'))

        conn = get_db_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO Users (Username, Password) VALUES (?, ?)",
                           (username, password))
            conn.commit()
            flash("注册成功，请登录")
            return redirect(url_for('login'))
        except Exception as e:
            print(f"注册失败: {e}")
            flash("注册失败，请重试")
        finally:
            conn.close()
    return render_template('register.html')


@app.route('/publish', methods=['GET', 'POST'])
def post_item():
    """发布商品"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        price = request.form.get('price')
        condition = request.form.get('condition')
        description = request.form.get('description')
        pickup_location = request.form.get('pickup_location')

        # 验证必填字段
        if not all([title, category, price, condition, pickup_location]):
            flash("请填写所有必填项")
            return redirect(url_for('post_item'))

        # 验证图片是否上传
        f = request.files.get('image')
        if not f or f.filename == '':
            flash("请上传商品图片")
            return redirect(url_for('post_item'))

        # 验证图片格式
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file_ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else ''
        if file_ext not in allowed_extensions:
            flash("只支持上传图片格式：png, jpg, jpeg, gif, webp")
            return redirect(url_for('post_item'))

        # 保存图片
        filename = secure_filename(f.filename)
        # 添加时间戳避免文件名冲突
        import time
        name, ext = filename.rsplit('.', 1)
        filename = f"{name}_{int(time.time())}.{ext}"
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO Items (Title, Category, SellerID, Price, Condition, PickupLocation, Description, ImagePath, Status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'available')
            """, (title, category, session['user_id'], price, condition, pickup_location, description, filename))
            conn.commit()
            flash("发布成功")
            return redirect(url_for('profile'))
        except Exception as e:
            print(f"数据库写入失败: {e}")
            flash("发布失败，请重试")
        finally:
            conn.close()

    return render_template('publish.html',
                           username=session.get('username'),
                           all_rooms=CAMPUS_ROOMS)

@app.route('/delete_item/<item_id>')
def delete_item(item_id):
    """删除商品"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    success = execute_db("DELETE FROM Items WHERE ItemID = ? AND SellerID = ?",
                         (item_id, session['user_id']))
    if success:
        flash("宝贝已删除")
    else:
        flash("删除失败或您无权删除此商品")
    return redirect(url_for('profile'))


@app.route('/edit_item/<item_id>')
def edit_item(item_id):
    """编辑商品页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    item = query_db("SELECT * FROM Items WHERE ItemID = ?", (item_id,), one=True)

    if not item:
        flash("未找到宝贝")
        return redirect(url_for('profile'))

    # 验证是否为卖家本人
    if item.get('sellerid') != session['user_id']:
        flash("您无权编辑此商品")
        return redirect(url_for('profile'))

    return render_template('edit_item.html',
                           item=item,
                           all_rooms=CAMPUS_ROOMS,
                           username=session.get('username'))


@app.route('/update_item/<item_id>', methods=['POST'])
def update_item(item_id):
    """更新商品信息"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    title = request.form.get('title')
    category = request.form.get('category')
    price = request.form.get('price')
    condition = request.form.get('condition')
    pickup_location = request.form.get('pickup_location')
    description = request.form.get('description')

    f = request.files.get('image')
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        if f and f.filename != '':
            filename = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cursor.execute("""
                UPDATE Items 
                SET Title=?, Category=?, Price=?, Condition=?, PickupLocation=?, Description=?, ImagePath=?
                WHERE ItemID=? AND SellerID=?
            """, (title, category, price, condition, pickup_location, description, filename,
                  item_id, session['user_id']))
        else:
            cursor.execute("""
                UPDATE Items 
                SET Title=?, Category=?, Price=?, Condition=?, PickupLocation=?, Description=?
                WHERE ItemID=? AND SellerID=?
            """, (title, category, price, condition, pickup_location, description,
                  item_id, session['user_id']))

        conn.commit()
        flash("宝贝信息已成功更新")
    except Exception as e:
        print(f"更新数据库失败: {e}")
        flash("更新失败，请检查数据格式")
    finally:
        conn.close()

    return redirect(url_for('profile'))


@app.route('/item/<item_id>')
def item_detail(item_id):
    """商品详情页"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    item = query_db("SELECT * FROM Items WHERE ItemID = ?", (item_id,), one=True)
    if not item:
        flash("商品不存在")
        return redirect(url_for('categories'))

    seller = query_db("SELECT Username FROM Users WHERE UserID = ?",
                      (item['sellerid'],), one=True)
    floor_plan = get_floor_image(item.get('pickuplocation'))

    return render_template('item_detail.html',
                           item=item,
                           seller_name=seller['username'] if seller else "未知用户",
                           floor_plan=floor_plan,
                           username=session.get('username'))


@app.route('/place_order/<item_id>', methods=['POST'])
def place_order(item_id):
    """下单购买"""
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': '请先登录'}), 401
        return redirect(url_for('login'))

    buyer_id = session['user_id']

    # 获取商品详情
    item = query_db("SELECT * FROM Items WHERE ItemID = ?", (item_id,), one=True)

    if not item:
        msg = "商品不存在"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': msg}), 404
        flash(msg)
        return redirect(url_for('categories'))

    if item.get('status') == 'sold':
        msg = "商品已售罄"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': msg}), 400
        flash(msg)
        return redirect(url_for('categories'))

    if item.get('sellerid') == buyer_id:
        msg = "不能购买自己的商品"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': msg}), 400
        flash(msg)
        return redirect(url_for('profile'))

    conn = get_db_conn()
    if not conn:
        msg = "数据库连接失败"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': msg}), 500
        flash(msg)
        return redirect(url_for('categories'))

    cursor = conn.cursor()
    try:
        # 开启事务
        cursor.execute("""
            INSERT INTO Orders (ItemID, BuyerID, SellerID, Price, Status, OrderTime) 
            VALUES (?, ?, ?, ?, 'completed', GETDATE())
        """, (item_id, buyer_id, item['sellerid'], item['price']))

        cursor.execute("UPDATE Items SET Status = 'sold' WHERE ItemID = ?", (item_id,))
        conn.commit()

        msg = "购买成功！"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg})
        flash(msg)
        return redirect(url_for('my_orders'))

    except Exception as e:
        print(f"交易异常: {e}")
        conn.rollback()
        msg = f"下单失败: {str(e)}"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': msg}), 500
        flash(msg)
        return redirect(url_for('categories'))
    finally:
        conn.close()


@app.route('/my_orders')
def my_orders():
    """订单中心"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']

    bought = query_db("""
        SELECT o.OrderID, o.ItemID, o.BuyerID, o.SellerID, o.Price, o.Status, o.OrderTime,
               i.Title, i.ImagePath,
               u.Username as sellername
        FROM Orders o
        JOIN Items i ON o.ItemID = i.ItemID
        JOIN Users u ON o.SellerID = u.UserID
        WHERE o.BuyerID = ? 
        ORDER BY o.OrderTime DESC
    """, (uid,)) or []

    sold = query_db("""
        SELECT o.OrderID, o.ItemID, o.BuyerID, o.SellerID, o.Price, o.Status, o.OrderTime,
               i.Title, i.ImagePath,
               u.Username as buyername
        FROM Orders o
        JOIN Items i ON o.ItemID = i.ItemID
        JOIN Users u ON o.BuyerID = u.UserID
        WHERE o.SellerID = ? 
        ORDER BY o.OrderTime DESC
    """, (uid,)) or []

    # 调试：打印数据类型
    if bought:
        print("bought order time type:", type(bought[0].get('ordertime')))
    if sold:
        print("sold order time type:", type(sold[0].get('ordertime')))

    return render_template('my_orders.html',
                           bought=bought,
                           sold=sold,
                           username=session.get('username'))

@app.route('/categories')
def categories():
    """商品分类页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cat = request.args.get('type')
    condition = request.args.get('condition')
    search_query = request.args.get('q')

    query = "SELECT * FROM Items WHERE Status = 'available'"
    params = []

    if search_query:
        query += " AND Title LIKE ?"
        params.append(f"%{search_query}%")
    elif cat:
        query += " AND Category = ?"
        params.append(cat)
    elif condition:
        query += " AND Condition = ?"
        params.append(condition)

    items = query_db(query, tuple(params)) or []
    return render_template('finding-product.html',
                           items=items,
                           username=session.get('username'))


@app.route('/profile')
def profile():
    """个人中心"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    uid = session['user_id']
    my_items = query_db("SELECT * FROM Items WHERE SellerID = ? ORDER BY ItemID DESC", (uid,)) or []

    return render_template('profile.html',
                           my_items=my_items,
                           username=session.get('username'))


@app.route('/chat/<item_id>/<int:partner_id>', methods=['GET', 'POST'])
def chat_detail(item_id, partner_id):
    """聊天详情页"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']

    # 验证商品存在
    item = query_db("SELECT ItemID, Title, SellerID, Status, Price FROM Items WHERE ItemID = ?", (item_id,), one=True)
    if not item:
        flash("商品不存在")
        return redirect(url_for('categories'))

    # 验证对方用户存在
    partner = query_db("SELECT Username, UserID FROM Users WHERE UserID = ?", (partner_id,), one=True)
    if not partner:
        flash("用户不存在")
        return redirect(url_for('messages'))

    # 处理发送消息
    if request.method == 'POST':
        content = request.form.get('content')
        if content and content.strip():
            # 使用 execute_db 函数执行插入
            success = execute_db("""
                INSERT INTO Messages (ItemID, SenderID, ReceiverID, Content, SendTime) 
                VALUES (?, ?, ?, ?, GETDATE())
            """, (item_id, uid, partner_id, content.strip()))

            if success:
                print(f"消息发送成功: {content}")
            else:
                print("消息发送失败")

        # 发送后重定向回聊天页面
        return redirect(url_for('chat_detail', item_id=item_id, partner_id=partner_id))

    # 获取聊天历史记录 - 修复查询逻辑
    history = query_db("""
        SELECT MessageID, ItemID, SenderID, ReceiverID, Content, SendTime
        FROM Messages 
        WHERE ItemID = ? AND 
        ((SenderID = ? AND ReceiverID = ?) OR (SenderID = ? AND ReceiverID = ?))
        ORDER BY SendTime ASC
    """, (item_id, uid, partner_id, partner_id, uid)) or []

    # 调试输出
    print(f"找到 {len(history)} 条消息记录")
    if history:
        for msg in history:
            print(f"消息: {msg.get('content')} - {msg.get('sendtime')}")

    return render_template('chat_detail.html',
                           history=history,
                           partner=partner,
                           item=item,
                           uid=uid)

# 在 app.py 的开头，app = Flask(__name__) 之后添加

# 自定义过滤器：格式化时间
@app.template_filter('format_datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    """格式化 datetime 对象或字符串"""
    if value is None:
        return ''
    if isinstance(value, str):
        # 如果是字符串，尝试截取前16个字符
        return value[:16] if len(value) > 16 else value
    if hasattr(value, 'strftime'):
        # 如果是 datetime 对象
        return value.strftime(format)
    return str(value)

# 简短时间格式（只显示时分）
@app.template_filter('format_time')
def format_time(value):
    """格式化时间为 HH:MM"""
    if value is None:
        return ''
    if isinstance(value, str):
        return value[11:16] if len(value) > 16 else value
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    return str(value)


@app.route('/messages')
def messages():
    """消息列表页 - 简化版"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']

    # 使用更简单的查询 - 直接获取所有相关消息，在Python中分组
    all_messages = query_db("""
        SELECT 
            m.ItemID,
            m.SenderID,
            m.ReceiverID,
            m.Content,
            m.SendTime,
            i.Title,
            CASE 
                WHEN m.SenderID = ? THEN m.ReceiverID 
                ELSE m.SenderID 
            END as partnerid
        FROM Messages m
        JOIN Items i ON m.ItemID = i.ItemID
        WHERE m.SenderID = ? OR m.ReceiverID = ?
        ORDER BY m.SendTime DESC
    """, (uid, uid, uid)) or []

    # 在Python中处理分组
    chats_dict = {}
    for msg in all_messages:
        key = f"{msg['itemid']}_{msg['partnerid']}"
        if key not in chats_dict:
            # 获取对方用户名
            partner_info = query_db("SELECT Username FROM Users WHERE UserID = ?",
                                    (msg['partnerid'],), one=True)
            chats_dict[key] = {
                'ItemID': msg['itemid'],
                'Title': msg['title'],
                'partnerid': msg['partnerid'],
                'partnername': partner_info['username'] if partner_info else '用户',
                'last_time': msg['sendtime'],
                'last_content': msg['content'][:50]
            }

    chats = list(chats_dict.values())
    chats.sort(key=lambda x: x['last_time'], reverse=True)

    return render_template('message.html',
                           username=session.get('username'),
                           chats=chats)


@app.route('/change_password', methods=['POST'])
def change_password():
    """修改密码"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    new_pwd = request.form.get('new_password')
    if not new_pwd or len(new_pwd) < 3:
        flash("密码长度至少3位")
        return redirect(url_for('profile'))

    success = execute_db("UPDATE Users SET Password = ? WHERE UserID = ?",
                         (new_pwd, session['user_id']))
    if success:
        flash("密码修改成功，请重新登录")
        session.clear()
        return redirect(url_for('login'))
    else:
        flash("修改密码失败")
        return redirect(url_for('profile'))


@app.route('/api/messages/<item_id>/<int:partner_id>')
def api_get_messages(item_id, partner_id):
    """获取消息的API接口 - 自动适配表结构"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})

    uid = session['user_id']

    # 先获取表结构信息
    try:
        # 尝试多种可能的列名
        messages = query_db("""
            SELECT * FROM Messages 
            WHERE ItemID = ? 
            ORDER BY SendTime ASC
        """, (item_id,)) or []

        # 如果上面失败，尝试不同的列名
        if not messages:
            messages = query_db("""
                SELECT * FROM Message 
                WHERE ItemID = ? 
                ORDER BY SendTime ASC
            """, (item_id,)) or []

        # 格式化返回数据
        formatted_messages = []
        for msg in messages:
            formatted_msg = {
                'content': msg.get('Content') or msg.get('content') or msg.get('MessageContent') or '',
                'senderid': msg.get('SenderID') or msg.get('senderid') or msg.get('SenderId'),
                'receiverid': msg.get('ReceiverID') or msg.get('receiverid') or msg.get('ReceiverId'),
                'sendtime': msg.get('SendTime') or msg.get('sendtime') or msg.get('SendDate')
            }

            # 格式化时间
            if formatted_msg['sendtime']:
                if hasattr(formatted_msg['sendtime'], 'strftime'):
                    formatted_msg['sendtime'] = formatted_msg['sendtime'].strftime('%Y-%m-%d %H:%M:%S')

            formatted_messages.append(formatted_msg)

        return jsonify({'success': True, 'messages': formatted_messages})

    except Exception as e:
        print(f"查询消息失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    """发送消息的API接口 - 自动适配"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})

    data = request.get_json()
    item_id = data.get('item_id')
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()

    if not content:
        return jsonify({'success': False, 'error': '消息内容不能为空'})

    uid = session['user_id']

    try:
        # 尝试多种插入语句
        try:
            # 尝试标准列名
            success = execute_db("""
                INSERT INTO Messages (ItemID, SenderID, ReceiverID, Content, SendTime) 
                VALUES (?, ?, ?, ?, GETDATE())
            """, (item_id, uid, receiver_id, content))
        except:
            # 尝试小写列名
            success = execute_db("""
                INSERT INTO Messages (itemid, senderid, receiverid, content, sendtime) 
                VALUES (?, ?, ?, ?, GETDATE())
            """, (item_id, uid, receiver_id, content))

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '发送失败'})

    except Exception as e:
        print(f"发送消息失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
