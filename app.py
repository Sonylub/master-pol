from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import psycopg2
import os
import bcrypt
from functools import wraps
import csv
import io
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-secret-key")

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Модель пользователя
class User(UserMixin):
    def __init__(self, user_id, username, email, role, partner_id=None):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.partner_id = partner_id

# Декоратор для проверки роли
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash("Доступ запрещён", "error")
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Подключение к базе данных
def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        print("Подключение к базе успешно!")
        return conn, {"status": "success", "message": "Подключение к базе данных успешно"}
    except Exception as e:
        print(f"Ошибка подключения: {str(e)}")
        return None, {"status": "error", "message": f"Ошибка подключения к базе: {str(e)}"}

# Загрузка пользователя
@login_manager.user_loader
def load_user(user_id):
    conn, db_status = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT UserID, Username, Email, Role, PartnerID FROM Users WHERE UserID = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user[0], user[1], user[2], user[3], user[4])
    return None

@app.route('/')
def index():
    conn, db_status = get_db_connection()
    if conn:
        conn.close()
    return render_template('index.html', db_status=db_status)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status["message"], "error")
            return render_template('login.html')
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, Username, Email, Password, Role, PartnerID FROM Users WHERE Username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and bcrypt.checkpw(password, user[3].encode('utf-8')):
            login_user(User(user[0], user[1], user[2], user[4], user[5]))
            flash("Вход выполнен успешно!", "success")
            return redirect(url_for('index'))
        flash("Неверное имя пользователя или пароль", "error")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        role = request.form.get('role', 'partner')
        partner_id = request.form.get('partner_id') or None
        if role == 'partner' and not partner_id:
            flash("Для роли 'partner' необходимо указать PartnerID", "error")
            return render_template('register.html')
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status["message"], "error")
            return render_template('register.html')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO Users (Username, Email, Password, Role, PartnerID) VALUES (%s, %s, %s, %s, %s)",
                (username, email, hashed_password, role, partner_id)
            )
            conn.commit()
            flash("Регистрация успешна! Войдите в систему.", "success")
            cursor.close()
            conn.close()
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Имя пользователя или email уже заняты", "error")
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Вы вышли из системы", "success")
    return redirect(url_for('index'))

@app.route('/partners', methods=['GET'])
@login_required
@role_required('analyst', 'manager')
def partners():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()

        # Параметры для поиска, фильтрации и сортировки
        search = request.args.get('search', '')
        rating_filter = request.args.get('rating_filter', '')
        sort = request.args.get('sort', 'name_asc')

        query = """
            SELECT PartnerID, Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating,
                   fn_GetPartnerDiscount(PartnerID) AS Discount
            FROM Partners
            WHERE 1=1
        """
        params = []

        # Поиск по наименованию
        if search:
            query += " AND Name ILIKE %s"
            params.append(f"%{search}%")

        # Фильтр по рейтингу
        if rating_filter:
            query += " AND Rating >= %s"
            params.append(float(rating_filter))

        # Сортировка
        if sort == 'name_asc':
            query += " ORDER BY Name ASC"
        elif sort == 'name_desc':
            query += " ORDER BY Name DESC"
        elif sort == 'rating_desc':
            query += " ORDER BY Rating DESC"
        elif sort == 'discount_desc':
            query += " ORDER BY fn_GetPartnerDiscount(PartnerID) DESC"

        cursor.execute(query, params)
        partners = cursor.fetchall()
        print(f"Найдено партнёров: {len(partners)}")
        for partner in partners:
            print(partner)
        cursor.close()
        conn.close()
        return render_template('partners.html', partners=partners)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Partners."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/add_partner', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def add_partner():
    if request.method == 'GET':
        flash("Пожалуйста, используйте форму для добавления партнёра", "error")
        return redirect(url_for('partners'))
    
    name = request.form['name']
    legal_address = request.form.get('legal_address') or None
    inn = request.form.get('inn') or None
    director_full_name = request.form.get('director_full_name') or None
    phone = request.form.get('phone') or None
    email = request.form.get('email') or None
    rating = float(request.form.get('rating', 0)) if request.form.get('rating') else None

    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status["message"], "error")
        return redirect(url_for('partners'))
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO Partners (Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (name, legal_address, inn, director_full_name, phone, email, rating)
        )
        conn.commit()
        flash("Партнёр успешно добавлен!", "success")
    except psycopg2.IntegrityError:
        conn.rollback()
        flash("Партнёр с таким именем или ИНН уже существует", "error")
    except Exception as e:
        conn.rollback()
        flash(f"Ошибка: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('partners'))

@app.route('/delete_partner', methods=['POST'])
@login_required
@role_required('manager')
def delete_partner():
    partner_id = request.form['partner_id']
    
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status["message"], "error")
        return redirect(url_for('partners'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Partners WHERE PartnerID = %s", (partner_id,))
        if cursor.rowcount == 0:
            flash("Партнёр не найден", "error")
        else:
            conn.commit()
            flash("Партнёр успешно удалён!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Ошибка удаления: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('partners'))

@app.route('/partner_requests/<int:partner_id>', methods=['GET'])
@login_required
@role_required('analyst', 'manager')
def partner_requests(partner_id):
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()
        
        # Получаем имя партнёра
        cursor.execute("SELECT Name FROM Partners WHERE PartnerID = %s", (partner_id,))
        partner = cursor.fetchone()
        if not partner:
            cursor.close()
            conn.close()
            flash("Партнёр не найден", "error")
            return redirect(url_for('partners'))
        
        partner_name = partner[0]
        
        # Получаем заявки партнёра
        cursor.execute("""
            SELECT r.RequestID, m.FullName AS ManagerName, pr.Name AS ProductName,
                   r.Quantity, r.UnitPrice, r.TotalPrice, r.Status, r.CreatedAt
            FROM Requests r
            JOIN Managers m ON r.ManagerID = m.ManagerID
            JOIN Products pr ON r.ProductID = pr.ProductID
            WHERE r.PartnerID = %s
        """, (partner_id,))
        requests = cursor.fetchall()
        print(f"Найдено заявок для партнёра {partner_id}: {len(requests)}")
        for req in requests:
            print(req)
        
        cursor.close()
        conn.close()
        return render_template('partner_requests.html', requests=requests, partner_name=partner_name)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Requests."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/my_requests', methods=['GET'])
@login_required
@role_required('partner')
def my_requests():
    try:
        if not current_user.partner_id:
            flash("У вас не указан PartnerID. Обратитесь к администратору.", "error")
            return redirect(url_for('index'))
        
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()
        
        # Получаем имя партнёра
        cursor.execute("SELECT Name FROM Partners WHERE PartnerID = %s", (current_user.partner_id,))
        partner = cursor.fetchone()
        if not partner:
            cursor.close()
            conn.close()
            flash("Партнёр не найден", "error")
            return redirect(url_for('index'))
        
        partner_name = partner[0]
        
        # Получаем заявки партнёра
        cursor.execute("""
            SELECT r.RequestID, m.FullName AS ManagerName, pr.Name AS ProductName,
                   r.Quantity, r.UnitPrice, r.TotalPrice, r.Status, r.CreatedAt
            FROM Requests r
            JOIN Managers m ON r.ManagerID = m.ManagerID
            JOIN Products pr ON r.ProductID = pr.ProductID
            WHERE r.PartnerID = %s
        """, (current_user.partner_id,))
        requests = cursor.fetchall()
        print(f"Найдено заявок для партнёра {current_user.partner_id}: {len(requests)}")
        for req in requests:
            print(req)
        
        cursor.close()
        conn.close()
        return render_template('partner_requests.html', requests=requests, partner_name=partner_name)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Requests."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/requests', methods=['GET'])
@login_required
@role_required('analyst', 'manager')
def requests():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.RequestID, p.Name AS PartnerName, m.FullName AS ManagerName, pr.Name AS ProductName,
                   r.Quantity, r.UnitPrice, r.TotalPrice, r.Status, r.CreatedAt
            FROM Requests r
            JOIN Partners p ON r.PartnerID = p.PartnerID
            JOIN Managers m ON r.ManagerID = m.ManagerID
            JOIN Products pr ON r.ProductID = pr.ProductID
        """)
        requests = cursor.fetchall()
        print(f"Найдено заявок: {len(requests)}")
        for req in requests:
            print(req)
        cursor.close()
        conn.close()
        return render_template('requests.html', requests=requests)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Requests."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/add_request', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def add_request():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()

        if request.method == 'POST':
            partner_id = request.form.get('partner_id')
            manager_id = request.form.get('manager_id')
            product_id = request.form.get('product_id')
            quantity = request.form.get('quantity')
            unit_price = request.form.get('unit_price')

            # Валидация
            try:
                quantity = int(quantity)
                unit_price = float(unit_price)
                partner_id = int(partner_id)
                manager_id = int(manager_id)
                product_id = int(product_id)
                if quantity <= 0:
                    flash("Количество должно быть больше 0", "error")
                    raise ValueError("Invalid quantity")
                if unit_price <= 0:
                    flash("Цена за единицу должна быть больше 0", "error")
                    raise ValueError("Invalid unit price")
            except ValueError:
                flash("Неверный формат данных", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('add_request'))

            # Проверка существования записей
            cursor.execute("SELECT 1 FROM Partners WHERE PartnerID = %s", (partner_id,))
            if not cursor.fetchone():
                flash("Партнёр не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('add_request'))
            cursor.execute("SELECT 1 FROM Managers WHERE ManagerID = %s", (manager_id,))
            if not cursor.fetchone():
                flash("Менеджер не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('add_request'))
            cursor.execute("SELECT 1 FROM Products WHERE ProductID = %s", (product_id,))
            if not cursor.fetchone():
                flash("Продукт не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('add_request'))

            # Вставка заявки
            try:
                cursor.execute(
                    """
                    INSERT INTO Requests (PartnerID, ManagerID, ProductID, Quantity, UnitPrice, Status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (partner_id, manager_id, product_id, quantity, unit_price, 'Новая')
                )
                conn.commit()
                flash("Заявка успешно добавлена!", "success")
            except Exception as e:
                conn.rollback()
                flash(f"Ошибка добавления заявки: {str(e)}", "error")
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('requests'))

        # Получение данных для формы
        cursor.execute("SELECT PartnerID, Name FROM Partners ORDER BY Name")
        partners = cursor.fetchall()
        cursor.execute("SELECT ManagerID, FullName FROM Managers ORDER BY FullName")
        managers = cursor.fetchall()
        cursor.execute("SELECT ProductID, Name FROM Products ORDER BY Name")
        products = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return render_template('add_request.html', partners=partners, managers=managers, products=products)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/supplies', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def supplies():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()

        if request.method == 'POST':
            supplier_id = request.form.get('supplier_id')
            material_id = request.form.get('material_id')
            manager_id = request.form.get('manager_id')
            quantity = request.form.get('quantity')

            # Валидация
            try:
                quantity = float(quantity)
                if quantity <= 0:
                    flash("Количество должно быть больше 0", "error")
                    raise ValueError("Invalid quantity")
                supplier_id = int(supplier_id)
                material_id = int(material_id)
                manager_id = int(manager_id)
            except ValueError:
                flash("Неверный формат данных", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('supplies'))

            # Проверка существования записей
            cursor.execute("SELECT 1 FROM Suppliers WHERE SupplierID = %s", (supplier_id,))
            if not cursor.fetchone():
                flash("Поставщик не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('supplies'))
            cursor.execute("SELECT 1 FROM Materials WHERE MaterialID = %s", (material_id,))
            if not cursor.fetchone():
                flash("Материал не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('supplies'))
            cursor.execute("SELECT 1 FROM Managers WHERE ManagerID = %s", (manager_id,))
            if not cursor.fetchone():
                flash("Менеджер не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('supplies'))

            # Вставка поставки
            try:
                cursor.execute(
                    """
                    INSERT INTO Supplies (SupplierID, MaterialID, ManagerID, Quantity)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (supplier_id, material_id, manager_id, quantity)
                )
                # Обновление количества материала на складе
                cursor.execute(
                    """
                    UPDATE Materials
                    SET QuantityInStock = QuantityInStock + %s
                    WHERE MaterialID = %s
                    """,
                    (quantity, material_id)
                )
                conn.commit()
                flash("Поставка успешно добавлена!", "success")
            except Exception as e:
                conn.rollback()
                flash(f"Ошибка добавления поставки: {str(e)}", "error")
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('supplies'))

        # Получение данных для формы и таблицы
        cursor.execute("SELECT SupplierID, Name FROM Suppliers ORDER BY Name")
        suppliers = cursor.fetchall()
        cursor.execute("SELECT MaterialID, Name FROM Materials ORDER BY Name")
        materials = cursor.fetchall()
        cursor.execute("SELECT ManagerID, FullName FROM Managers ORDER BY FullName")
        managers = cursor.fetchall()
        cursor.execute("""
            SELECT s.SupplyID, sup.Name AS SupplierName, m.Name AS MaterialName, 
                   man.FullName AS ManagerName, s.Quantity, s.SupplyDate
            FROM Supplies s
            JOIN Suppliers sup ON s.SupplierID = sup.SupplierID
            JOIN Materials m ON s.MaterialID = m.MaterialID
            JOIN Managers man ON s.ManagerID = man.ManagerID
            ORDER BY s.SupplyDate DESC
        """)
        supplies = cursor.fetchall()
        print(f"Найдено поставок: {len(supplies)}")
        for supply in supplies:
            print(supply)
        
        cursor.close()
        conn.close()
        return render_template('supplies.html', supplies=supplies, suppliers=suppliers, materials=materials, managers=managers)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Supplies."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/products', methods=['GET'])
@login_required
@role_required('analyst', 'manager')
def products():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ProductID, Name, Description, StandardNumber, ManufactureTimeDays, 
                   CostPrice, MinPartnerPrice, CreatedAt
            FROM Products
            ORDER BY Name
        """)
        products = cursor.fetchall()
        print(f"Найдено продукции: {len(products)}")
        for product in products:
            print(product)
        cursor.close()
        conn.close()
        return render_template('products.html', products=products)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Products."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/materials', methods=['GET'])
@login_required
@role_required('analyst', 'manager')
def materials():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MaterialID, Name, Unit, Cost, QuantityInStock, MinAllowedQuantity
            FROM Materials
            ORDER BY Name
        """)
        materials = cursor.fetchall()
        print(f"Найдено материалов: {len(materials)}")
        for material in materials:
            print(material)
        cursor.close()
        conn.close()
        return render_template('materials.html', materials=materials)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Materials."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def upload():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash("Файл не выбран", "error")
            return redirect(url_for('upload'))
        
        file = request.files['csv_file']
        if not file.filename.endswith('.csv'):
            flash("Файл должен быть в формате CSV", "error")
            return redirect(url_for('upload'))
        
        try:
            # Читаем CSV-файл
            stream = io.StringIO(file.stream.read().decode("utf-8"))
            csv_reader = csv.DictReader(stream)
            expected_columns = {'Name', 'LegalAddress', 'INN', 'DirectorFullName', 'Phone', 'Email', 'Rating'}
            
            # Проверка заголовков
            if not expected_columns.issubset(csv_reader.fieldnames):
                flash("Неверный формат CSV. Ожидаемые столбцы: Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating", "error")
                return redirect(url_for('upload'))
            
            conn, db_status = get_db_connection()
            if not conn:
                flash(db_status["message"], "error")
                return redirect(url_for('upload'))
            
            cursor = conn.cursor()
            inserted = 0
            errors = []

            # Валидация и вставка данных
            for row_num, row in enumerate(csv_reader, start=2):
                name = row['Name'].strip()
                legal_address = row['LegalAddress'].strip() or None
                inn = row['INN'].strip() or None
                director_full_name = row['DirectorFullName'].strip() or None
                phone = row['Phone'].strip() or None
                email = row['Email'].strip() or None
                rating = row['Rating'].strip() or None

                # Валидация
                if not name:
                    errors.append(f"Строка {row_num}: Поле Name обязательно")
                    continue
                if not inn:
                    errors.append(f"Строка {row_num}: Поле INN обязательно")
                    continue
                if inn and not re.match(r'^\d{10,12}$', inn):
                    errors.append(f"Строка {row_num}: INN должен содержать 10 или 12 цифр")
                    continue
                if phone and not re.match(r'^\+?\d{10,15}$', phone):
                    errors.append(f"Строка {row_num}: Телефон должен содержать 10–15 цифр")
                    continue
                if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                    errors.append(f"Строка {row_num}: Неверный формат Email")
                    continue
                if rating:
                    try:
                        rating = float(rating)
                        if not 0 <= rating <= 5:
                            errors.append(f"Строка {row_num}: Рейтинг должен быть от 0 до 5")
                            continue
                    except ValueError:
                        errors.append(f"Строка {row_num}: Рейтинг должен быть числом")
                        continue
                else:
                    rating = None

                # Вставка в базу
                try:
                    cursor.execute(
                        """
                        INSERT INTO Partners (Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (name, legal_address, inn, director_full_name, phone, email, rating)
                    )
                    inserted += 1
                except psycopg2.IntegrityError:
                    conn.rollback()
                    errors.append(f"Строка {row_num}: Партнёр с именем '{name}' или ИНН '{inn}' уже существует")
                except Exception as e:
                    conn.rollback()
                    errors.append(f"Строка {row_num}: Ошибка: {str(e)}")

            if inserted > 0:
                conn.commit()
                flash(f"Успешно импортировано {inserted} партнёров", "success")
            if errors:
                flash("\n".join(errors), "error")
            
            cursor.close()
            conn.close()
            return redirect(url_for('upload'))
        
        except Exception as e:
            flash(f"Ошибка обработки файла: {str(e)}", "error")
            return redirect(url_for('upload'))
    
    return render_template('upload.html')

@app.route('/calc', methods=['GET', 'POST'])
@login_required
@role_required('analyst', 'manager')
def calc():
    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        material_id = int(request.form['material_id'])
        quantity = int(request.form['quantity'])
        param1 = float(request.form['param1'])
        param2 = float(request.form['param2'])
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status["message"], "error")
            return render_template('calc.html')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT fn_CalcRequiredMaterial(%s, %s, %s, %s, %s)",
            (product_id, material_id, quantity, param1, param2)
        )
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        flash(f"Требуется материалов: {result}", "success")
        return render_template('calc.html', result=result)
    return render_template('calc.html')

if __name__ == '__main__':
    app.run(debug=True)