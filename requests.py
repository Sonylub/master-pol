from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from db import get_db_connection
import logging
from werkzeug.exceptions import abort

requests_bp = Blueprint('requests', __name__)
logger = logging.getLogger(__name__)

@requests_bp.route('/requests', methods=['GET'])
@login_required
def requests():
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    conn, db_status = get_db_connection()
    if not conn:
        return render_template('requests.html', requests=[], db_status=db_status)
    cursor = conn.cursor()
    try:
        search = request.args.get('search', '')
        status_filter = request.args.get('status_filter', '')
        sort = request.args.get('sort', 'created_at_desc')

        query = """
            SELECT r.RequestID, p.Name AS PartnerName, m.FullName AS ManagerName, pr.Name AS ProductName,
                   r.Quantity, r.UnitPrice, r.TotalPrice, r.Status, r.CreatedAt
            FROM Requests r
            JOIN Partners p ON r.PartnerID = p.PartnerID
            JOIN Managers m ON r.ManagerID = m.ManagerID
            JOIN Products pr ON r.ProductID = pr.ProductID
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND p.Name ILIKE %s"
            params.append(f"%{search}%")

        if status_filter:
            query += " AND r.Status = %s"
            params.append(status_filter)

        if sort == 'created_at_desc':
            query += " ORDER BY r.CreatedAt DESC"
        elif sort == 'created_at_asc':
            query += " ORDER BY r.CreatedAt ASC"
        elif sort == 'total_price_desc':
            query += " ORDER BY r.TotalPrice DESC"
        elif sort == 'total_price_asc':
            query += " ORDER BY r.TotalPrice ASC"
        elif sort == 'partner_name_asc':
            query += " ORDER BY p.Name ASC"
        elif sort == 'partner_name_desc':
            query += " ORDER BY p.Name DESC"

        cursor.execute(query, params)
        requests = cursor.fetchall()
        logger.info(f"Найдено заявок: {len(requests)}")

        cursor.execute("SELECT DISTINCT Status FROM Requests")
        statuses = [row[0] for row in cursor.fetchall()]
        
        return render_template('requests.html', requests=requests, db_status=db_status, statuses=statuses)
    except Exception as e:
        logger.error(f"Ошибка при получении заявок: {str(e)}")
        return render_template('requests.html', requests=[], db_status={'status': 'error', 'message': str(e)}, statuses=[])
    finally:
        cursor.close()
        conn.close()

@requests_bp.route('/my_requests')
@login_required
def my_requests():
    if current_user.role != 'partner':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    if not current_user.partner_id:
        logger.error(f"Пользователь {current_user.username} не привязан к партнёру")
        return render_template('my_requests.html', requests=[], db_status={'status': 'error', 'message': 'Пользователь не привязан к партнёру'})
    conn, db_status = get_db_connection()
    if not conn:
        return render_template('my_requests.html', requests=[], db_status=db_status)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT r.RequestID, p.Name AS PartnerName, m.FullName AS ManagerName, pr.Name AS ProductName,
                   r.Quantity, r.UnitPrice, r.TotalPrice, r.Status, r.CreatedAt
            FROM Requests r
            JOIN Partners p ON r.PartnerID = p.PartnerID
            JOIN Managers m ON r.ManagerID = m.ManagerID
            JOIN Products pr ON r.ProductID = pr.ProductID
            WHERE r.PartnerID = %s AND r.Status = 'Выполнена'
            """,
            (current_user.partner_id,)
        )
        requests = cursor.fetchall()
        logger.info(f"Найдено заявок для партнёра {current_user.partner_id}: {len(requests)}")
        return render_template('my_requests.html', requests=requests, db_status=db_status)
    except Exception as e:
        logger.error(f"Ошибка при получении истории реализации: {str(e)}")
        return render_template('my_requests.html', requests=[], db_status={'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@requests_bp.route('/add_request', methods=['GET', 'POST'])
@login_required
def add_request():
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    if request.method == 'POST':
        partner_id = request.form['partner_id']
        product_id = request.form['product_id']
        quantity = float(request.form['quantity'])
        unit_price = float(request.form['unit_price'])
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status['message'], 'error')
            return redirect(url_for('requests.add_request'))
        cursor = conn.cursor()
        try:
            # Проверка UnitPrice с учётом MinPartnerPrice и скидки
            cursor.execute("SELECT MinPartnerPrice FROM Products WHERE ProductID = %s", (product_id,))
            min_partner_price = cursor.fetchone()
            if not min_partner_price:
                flash('Продукт не найден', 'error')
                return redirect(url_for('requests.add_request'))
            min_partner_price = min_partner_price[0]
            
            cursor.execute("SELECT fn_GetPartnerDiscountNew(%s)", (partner_id,))
            discount = cursor.fetchone()[0] or 0
            discounted_min_price = min_partner_price * (1 - discount)
            
            if unit_price < discounted_min_price:
                flash(f'Цена за единицу не может быть ниже {discounted_min_price:.2f} (с учётом скидки {discount*100:.0f}%)', 'error')
                return redirect(url_for('requests.add_request'))
            
            cursor.execute(
                """
                INSERT INTO Requests (PartnerID, ManagerID, ProductID, Quantity, UnitPrice, Status, CreatedAt)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (partner_id, 1, product_id, quantity, unit_price, 'pending')
            )
            conn.commit()
            flash('Заявка успешно создана', 'success')
            return redirect(url_for('requests.requests'))
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при создании заявки: {str(e)}")
            flash(f'Ошибка: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
    conn, db_status = get_db_connection()
    if not conn:
        return render_template('add_request.html', partners=[], products=[], db_status=db_status)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT PartnerID, Name FROM Partners")
        partners = cursor.fetchall()
        cursor.execute("SELECT ProductID, Name FROM Products")
        products = cursor.fetchall()
        return render_template('add_request.html', partners=partners, products=products, db_status=db_status)
    except Exception as e:
        logger.error(f"Ошибка при получении данных: {str(e)}")
        return render_template('add_request.html', partners=[], products=[], db_status={'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@requests_bp.route('/edit_request/<int:request_id>', methods=['GET', 'POST'])
@login_required
def edit_request(request_id):
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status['message'], 'error')
        return redirect(url_for('requests.requests'))
    cursor = conn.cursor()
    if request.method == 'POST':
        partner_id = request.form['partner_id']
        product_id = request.form['product_id']
        quantity = float(request.form['quantity'])
        unit_price = float(request.form['unit_price'])
        status = request.form['status']
        try:
            # Проверка UnitPrice с учётом MinPartnerPrice и скидки
            cursor.execute("SELECT MinPartnerPrice FROM Products WHERE ProductID = %s", (product_id,))
            min_partner_price = cursor.fetchone()
            if not min_partner_price:
                flash('Продукт не найден', 'error')
                return redirect(url_for('requests.requests'))
            min_partner_price = min_partner_price[0]
            
            cursor.execute("SELECT fn_GetPartnerDiscountNew(%s)", (partner_id,))
            discount = cursor.fetchone()[0] or 0
            discounted_min_price = min_partner_price * (1 - discount)
            
            if unit_price < discounted_min_price:
                flash(f'Цена за единицу не может быть ниже {discounted_min_price:.2f} (с учётом скидки {discount*100:.0f}%)', 'error')
                return redirect(url_for('requests.requests'))
            
            cursor.execute(
                """
                UPDATE Requests
                SET PartnerID = %s, ProductID = %s, Quantity = %s, UnitPrice = %s, Status = %s
                WHERE RequestID = %s
                """,
                (partner_id, product_id, quantity, unit_price, status, request_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                flash('Заявка не найдена', 'error')
            else:
                conn.commit()
                flash('Заявка успешно обновлена', 'success')
            return redirect(url_for('requests.requests'))
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при обновлении заявки {request_id}: {str(e)}")
            flash(f'Ошибка: {str(e)}', 'error')
            return redirect(url_for('requests.requests'))
        finally:
            cursor.close()
            conn.close()
    try:
        cursor.execute(
            """
            SELECT r.RequestID, r.PartnerID, p.Name AS PartnerName, r.ProductID, pr.Name AS ProductName,
                   r.Quantity, r.UnitPrice, r.Status
            FROM Requests r
            JOIN Partners p ON r.PartnerID = p.PartnerID
            JOIN Products pr ON r.ProductID = pr.ProductID
            WHERE r.RequestID = %s
            """,
            (request_id,)
        )
        request_data = cursor.fetchone()
        if not request_data:
            cursor.close()
            conn.close()
            flash('Заявка не найдена', 'error')
            return redirect(url_for('requests.requests'))
        
        cursor.execute("SELECT PartnerID, Name FROM Partners")
        partners = cursor.fetchall()
        cursor.execute("SELECT ProductID, Name FROM Products")
        products = cursor.fetchall()
        cursor.execute("SELECT DISTINCT Status FROM Requests")
        statuses = [row[0] for row in cursor.fetchall()]
        
        return render_template('edit_request.html', request_data=request_data, partners=partners, products=products, statuses=statuses, db_status=db_status)
    except Exception as e:
        logger.error(f"Ошибка при получении данных для редактирования заявки {request_id}: {str(e)}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('requests.requests'))
    finally:
        cursor.close()
        conn.close()