from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import role_required
from db import get_db_connection
import logging
from werkzeug.exceptions import abort
import psycopg2

calc_bp = Blueprint('calc', __name__)
logger = logging.getLogger(__name__)

@calc_bp.route('/calc', methods=['GET', 'POST'])
@login_required
@role_required('analyst', 'manager', 'partner')
def calc():
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status['message'], 'error')
        return render_template('calc.html', products_materials=[], products=[], materials=[])

    cursor = conn.cursor()
    try:
        # Получение списка продуктов и материалов для формы
        cursor.execute("SELECT ProductID, Name FROM Products ORDER BY Name")
        products = cursor.fetchall()
        cursor.execute("SELECT MaterialID, Name FROM Materials ORDER BY Name")
        materials = cursor.fetchall()

        # Поиск и сортировка связей
        search_product = request.args.get('search_product', '')
        search_material = request.args.get('search_material', '')
        sort = request.args.get('sort', 'product_name_asc')

        query = """
            SELECT pc.ProductID, p.Name AS ProductName, pc.MaterialID, m.Name AS MaterialName, pc.Quantity
            FROM ProductComposition pc
            JOIN Products p ON pc.ProductID = p.ProductID
            JOIN Materials m ON pc.MaterialID = m.MaterialID
            WHERE 1=1
        """
        params = []

        if search_product:
            query += " AND p.Name ILIKE %s"
            params.append(f"%{search_product}%")
        if search_material:
            query += " AND m.Name ILIKE %s"
            params.append(f"%{search_material}%")

        if sort == 'product_name_asc':
            query += " ORDER BY p.Name ASC"
        elif sort == 'product_name_desc':
            query += " ORDER BY p.Name DESC"
        elif sort == 'material_name_asc':
            query += " ORDER BY m.Name ASC"
        elif sort == 'material_name_desc':
            query += " ORDER BY m.Name DESC"
        elif sort == 'quantity_desc':
            query += " ORDER BY pc.Quantity DESC"
        elif sort == 'quantity_asc':
            query += " ORDER BY pc.Quantity ASC"

        cursor.execute(query, params)
        products_materials = cursor.fetchall()

        # Обработка формы расчёта
        result = None
        if request.method == 'POST' and current_user.role in ['analyst', 'manager']:
            try:
                product_id = int(request.form['product_id'])
                material_id = int(request.form['material_id'])
                quantity = int(request.form['quantity'])
                param1 = float(request.form['param1'])
                param2 = float(request.form['param2'])
                
                cursor.execute(
                    "SELECT fn_CalcRequiredMaterial(%s, %s, %s, %s, %s)",
                    (product_id, material_id, quantity, param1, param2)
                )
                result = cursor.fetchone()[0]
                flash(f"Требуется материалов: {result}", "success")
            except psycopg2.Error as e:
                flash(f"Ошибка расчёта: {str(e)}", "error")
            except ValueError:
                flash("Неверный формат данных", "error")

        return render_template(
            'calc.html',
            products_materials=products_materials,
            products=products,
            materials=materials,
            result=result,
            db_status={'status': 'success', 'message': 'OK'}
        )
    except Exception as e:
        logger.error(f"Ошибка в /calc: {str(e)}")
        flash(f"Ошибка: {str(e)}", "error")
        return render_template(
            'calc.html',
            products_materials=[],
            products=[],
            materials=[],
            db_status={'status': 'error', 'message': str(e)}
        )
    finally:
        cursor.close()
        conn.close()

@calc_bp.route('/add_product_material', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def add_product_material():
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status['message'], 'error')
        return redirect(url_for('calc.calc'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ProductID, Name FROM Products ORDER BY Name")
        products = cursor.fetchall()
        cursor.execute("SELECT MaterialID, Name FROM Materials ORDER BY Name")
        materials = cursor.fetchall()

        if request.method == 'POST':
            product_id = int(request.form['product_id'])
            material_id = int(request.form['material_id'])
            quantity = float(request.form['quantity'])
            
            try:
                cursor.execute(
                    """
                    INSERT INTO ProductComposition (ProductID, MaterialID, Quantity)
                    VALUES (%s, %s, %s)
                    """,
                    (product_id, material_id, quantity)
                )
                conn.commit()
                flash('Связь продукт-материал успешно добавлена', 'success')
                return redirect(url_for('calc.calc'))
            except psycopg2.IntegrityError:
                conn.rollback()
                flash('Такая связь уже существует или указаны неверные ID', 'error')
            except Exception as e:
                conn.rollback()
                logger.error(f"Ошибка при добавлении связи: {str(e)}")
                flash(f'Ошибка: {str(e)}', 'error')

        return render_template('add_product_material.html', products=products, materials=materials, db_status=db_status)
    except Exception as e:
        logger.error(f"Ошибка в /add_product_material: {str(e)}")
        flash(f"Ошибка: {str(e)}", "error")
        return redirect(url_for('calc.calc'))
    finally:
        cursor.close()
        conn.close()

@calc_bp.route('/edit_product_material/<int:product_id>/<int:material_id>', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def edit_product_material(product_id, material_id):
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status['message'], 'error')
        return redirect(url_for('calc.calc'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ProductID, Name FROM Products ORDER BY Name")
        products = cursor.fetchall()
        cursor.execute("SELECT MaterialID, Name FROM Materials ORDER BY Name")
        materials = cursor.fetchall()

        if request.method == 'POST':
            quantity = float(request.form['quantity'])
            try:
                cursor.execute(
                    """
                    UPDATE ProductComposition
                    SET Quantity = %s
                    WHERE ProductID = %s AND MaterialID = %s
                    """,
                    (quantity, product_id, material_id)
                )
                if cursor.rowcount == 0:
                    conn.rollback()
                    flash('Связь не найдена', 'error')
                else:
                    conn.commit()
                    flash('Связь продукт-материал успешно обновлена', 'success')
                return redirect(url_for('calc.calc'))
            except Exception as e:
                conn.rollback()
                logger.error(f"Ошибка при обновлении связи {product_id}-{material_id}: {str(e)}")
                flash(f'Ошибка: {str(e)}', 'error')
                return redirect(url_for('calc.calc'))

        cursor.execute(
            """
            SELECT pc.ProductID, p.Name AS ProductName, pc.MaterialID, m.Name AS MaterialName, pc.Quantity
            FROM ProductComposition pc
            JOIN Products p ON pc.ProductID = p.ProductID
            JOIN Materials m ON pc.MaterialID = m.MaterialID
            WHERE pc.ProductID = %s AND pc.MaterialID = %s
            """,
            (product_id, material_id)
        )
        product_material = cursor.fetchone()
        if not product_material:
            flash('Связь не найдена', 'error')
            return redirect(url_for('calc.calc'))
        
        return render_template(
            'edit_product_material.html',
            product_material=product_material,
            products=products,
            materials=materials,
            db_status=db_status
        )
    except Exception as e:
        logger.error(f"Ошибка в /edit_product_material: {str(e)}")
        flash(f"Ошибка: {str(e)}", "error")
        return redirect(url_for('calc.calc'))
    finally:
        cursor.close()
        conn.close()

@calc_bp.route('/delete_product_material', methods=['POST'])
@login_required
@role_required('manager')
def delete_product_material():
    product_id = request.form['product_id']
    material_id = request.form['material_id']
    
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status['message'], 'error')
        return redirect(url_for('calc.calc'))
    
    cursor = conn.cursor()
    try:
        # Проверяем, есть ли связанные заявки
        cursor.execute("SELECT COUNT(*) FROM Requests WHERE ProductID = %s", (product_id,))
        request_count = cursor.fetchone()[0]
        if request_count > 0:
            conn.rollback()
            flash("Нельзя удалить связь, так как продукт используется в заявках", "error")
            return redirect(url_for('calc.calc'))
        
        cursor.execute(
            "DELETE FROM ProductComposition WHERE ProductID = %s AND MaterialID = %s",
            (product_id, material_id)
        )
        if cursor.rowcount == 0:
            flash("Связь не найдена", "error")
        else:
            conn.commit()
            flash("Связь продукт-материал успешно удалена!", "success")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Ошибка удаления связи {product_id}-{material_id}: {str(e)}")
        flash(f"Ошибка удаления: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('calc.calc'))