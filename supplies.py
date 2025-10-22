from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import role_required
from db import get_db_connection
import logging

supplies_bp = Blueprint('supplies', __name__)
logger = logging.getLogger(__name__)

@supplies_bp.route('/supplies', methods=['GET', 'POST'])
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
                return redirect(url_for('supplies.supplies'))

            cursor.execute("SELECT 1 FROM Suppliers WHERE SupplierID = %s", (supplier_id,))
            if not cursor.fetchone():
                flash("Поставщик не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('supplies.supplies'))
            cursor.execute("SELECT 1 FROM Materials WHERE MaterialID = %s", (material_id,))
            if not cursor.fetchone():
                flash("Материал не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('supplies.supplies'))
            cursor.execute("SELECT 1 FROM Managers WHERE ManagerID = %s", (manager_id,))
            if not cursor.fetchone():
                flash("Менеджер не найден", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('supplies.supplies'))

            try:
                cursor.execute(
                    """
                    INSERT INTO Supplies (SupplierID, MaterialID, ManagerID, Quantity)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (supplier_id, material_id, manager_id, quantity)
                )
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
            return redirect(url_for('supplies.supplies'))

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
        logger.info(f"Найдено поставок: {len(supplies)}")
        
        cursor.close()
        conn.close()
        return render_template('supplies.html', supplies=supplies, suppliers=suppliers, materials=materials, managers=managers)
    except Exception as e:
        logger.error(f"Ошибка в /supplies: {str(e)}")
        return render_template('error.html', error=f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Supplies.")