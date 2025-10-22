from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from db import get_db_connection
import logging
from werkzeug.exceptions import abort
import psycopg2

products_bp = Blueprint('products', __name__)
logger = logging.getLogger(__name__)

@products_bp.route('/products', methods=['GET'])
@login_required
def products():
    if current_user.role not in ['manager', 'partner']:
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    conn, db_status = get_db_connection()
    if not conn:
        return render_template('products.html', products=[], db_status=db_status)
    cursor = conn.cursor()
    try:
        search = request.args.get('search', '')
        sort = request.args.get('sort', 'name_asc')

        query = """
            SELECT ProductID, Name, Description, StandardNumber, ManufactureTimeDays, 
                   CostPrice, MinPartnerPrice, CreatedAt
            FROM Products
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND Name ILIKE %s"
            params.append(f"%{search}%")

        if sort == 'name_asc':
            query += " ORDER BY Name ASC"
        elif sort == 'name_desc':
            query += " ORDER BY Name DESC"
        elif sort == 'min_price_desc':
            query += " ORDER BY MinPartnerPrice DESC"
        elif sort == 'min_price_asc':
            query += " ORDER BY MinPartnerPrice ASC"

        cursor.execute(query, params)
        products = cursor.fetchall()
        logger.info(f"Найдено продуктов: {len(products)}")
        return render_template('products.html', products=products, db_status=db_status)
    except Exception as e:
        logger.error(f"Ошибка при получении продукции: {str(e)}")
        return render_template('products.html', products=[], db_status={'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@products_bp.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description') or None
        standard_number = request.form.get('standard_number') or None
        manufacture_time_days = request.form.get('manufacture_time_days') or None
        cost_price = float(request.form['cost_price']) if request.form.get('cost_price') else None
        min_partner_price = float(request.form['min_partner_price']) if request.form.get('min_partner_price') else None
        
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status['message'], 'error')
            return redirect(url_for('products.products'))
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO Products (Name, Description, StandardNumber, ManufactureTimeDays, CostPrice, MinPartnerPrice, CreatedAt)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (name, description, standard_number, manufacture_time_days, cost_price, min_partner_price)
            )
            conn.commit()
            flash('Продукт успешно добавлен', 'success')
            return redirect(url_for('products.products'))
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при создании продукта: {str(e)}")
            flash(f'Ошибка: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
    return render_template('add_product.html', db_status={'status': 'success', 'message': 'OK'})

@products_bp.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status['message'], 'error')
        return redirect(url_for('products.products'))
    cursor = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description') or None
        standard_number = request.form.get('standard_number') or None
        manufacture_time_days = request.form.get('manufacture_time_days') or None
        cost_price = float(request.form['cost_price']) if request.form.get('cost_price') else None
        min_partner_price = float(request.form['min_partner_price']) if request.form.get('min_partner_price') else None
        try:
            cursor.execute(
                """
                UPDATE Products
                SET Name = %s, Description = %s, StandardNumber = %s, ManufactureTimeDays = %s, 
                    CostPrice = %s, MinPartnerPrice = %s
                WHERE ProductID = %s
                """,
                (name, description, standard_number, manufacture_time_days, cost_price, min_partner_price, product_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                flash('Продукт не найден', 'error')
            else:
                conn.commit()
                flash('Продукт успешно обновлён', 'success')
            return redirect(url_for('products.products'))
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при обновлении продукта {product_id}: {str(e)}")
            flash(f'Ошибка: {str(e)}', 'error')
            return redirect(url_for('products.products'))
        finally:
            cursor.close()
            conn.close()
    try:
        cursor.execute(
            """
            SELECT ProductID, Name, Description, StandardNumber, ManufactureTimeDays, CostPrice, MinPartnerPrice, CreatedAt
            FROM Products
            WHERE ProductID = %s
            """,
            (product_id,)
        )
        product = cursor.fetchone()
        if not product:
            cursor.close()
            conn.close()
            flash('Продукт не найден', 'error')
            return redirect(url_for('products.products'))
        return render_template('edit_product.html', product=product, db_status=db_status)
    except Exception as e:
        logger.error(f"Ошибка при получении продукта {product_id}: {str(e)}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('products.products'))
    finally:
        cursor.close()
        conn.close()

@products_bp.route('/delete_product', methods=['POST'])
@login_required
def delete_product():
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    product_id = request.form['product_id']
    
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status['message'], 'error')
        return redirect(url_for('products.products'))
    
    cursor = conn.cursor()
    try:
        # Проверяем, есть ли заявки, связанные с продуктом
        cursor.execute("SELECT COUNT(*) FROM Requests WHERE ProductID = %s", (product_id,))
        request_count = cursor.fetchone()[0]
        if request_count > 0:
            conn.rollback()
            flash("Нельзя удалить продукт, так как он используется в заявках", "error")
            return redirect(url_for('products.products'))
        
        cursor.execute("DELETE FROM Products WHERE ProductID = %s", (product_id,))
        if cursor.rowcount == 0:
            flash("Продукт не найден", "error")
        else:
            conn.commit()
            flash("Продукт успешно удалён!", "success")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Ошибка удаления продукта {product_id}: {str(e)}")
        flash(f"Ошибка удаления: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('products.products'))