from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import role_required
from db import get_db_connection
import logging
import psycopg2

partners_bp = Blueprint('partners', __name__)
logger = logging.getLogger(__name__)

@partners_bp.route('/partners', methods=['GET'])
@login_required
@role_required('analyst', 'manager')
def partners():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()

        search = request.args.get('search', '')
        rating_filter = request.args.get('rating_filter', '')
        sort = request.args.get('sort', 'name_asc')

        query = """
            SELECT PartnerID, Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating,
                   fn_GetPartnerDiscountNew(PartnerID) AS Discount
            FROM Partners
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND Name ILIKE %s"
            params.append(f"%{search}%")

        if rating_filter:
            query += " AND Rating >= %s"
            params.append(float(rating_filter))

        if sort == 'name_asc':
            query += " ORDER BY Name ASC"
        elif sort == 'name_desc':
            query += " ORDER BY Name DESC"
        elif sort == 'rating_desc':
            query += " ORDER BY Rating DESC"
        elif sort == 'discount_desc':
            query += " ORDER BY fn_GetPartnerDiscountNew(PartnerID) DESC"

        cursor.execute(query, params)
        partners = cursor.fetchall()

        # Запрашиваем пользователей для каждого партнёра
        users_by_partner = {}
        for partner in partners:
            partner_id = partner[0]
            cursor.execute(
                "SELECT UserID, Username, Email, Role FROM Users WHERE PartnerID = %s",
                (partner_id,)
            )
            users = cursor.fetchall()
            users_by_partner[partner_id] = users

        logger.info(f"Найдено партнёров: {len(partners)}")
        cursor.close()
        conn.close()
        return render_template('partners.html', partners=partners, users_by_partner=users_by_partner)
    except Exception as e:
        logger.error(f"Ошибка в /partners: {str(e)}")
        return render_template('error.html', error=f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Partners.")

@partners_bp.route('/add_partner', methods=['POST'])
@login_required
@role_required('manager')
def add_partner():
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
        return redirect(url_for('partners.partners'))

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
    
    return redirect(url_for('partners.partners'))

@partners_bp.route('/delete_partner', methods=['POST'])
@login_required
@role_required('manager')
def delete_partner():
    partner_id = request.form['partner_id']
    
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status["message"], "error")
        return redirect(url_for('partners.partners'))
    
    cursor = conn.cursor()
    try:
        # Проверяем, есть ли пользователи, связанные с партнёром
        cursor.execute("SELECT COUNT(*) FROM Users WHERE PartnerID = %s", (partner_id,))
        user_count = cursor.fetchone()[0]
        if user_count > 0:
            conn.rollback()
            flash("Нельзя удалить партнёра, так как к нему привязаны пользователи", "error")
            return redirect(url_for('partners.partners'))
        
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
    
    return redirect(url_for('partners.partners'))

@partners_bp.route('/partner_requests/<int:partner_id>', methods=['GET'])
@login_required
@role_required('analyst', 'manager')
def partner_requests(partner_id):
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()
        
        cursor.execute("SELECT Name FROM Partners WHERE PartnerID = %s", (partner_id,))
        partner = cursor.fetchone()
        if not partner:
            cursor.close()
            conn.close()
            flash("Партнёр не найден", "error")
            return redirect(url_for('partners.partners'))
        
        partner_name = partner[0]
        
        cursor.execute("""
            SELECT r.RequestID, m.FullName AS ManagerName, pr.Name AS ProductName,
                   r.Quantity, r.UnitPrice, r.TotalPrice, r.Status, r.CreatedAt
            FROM Requests r
            JOIN Managers m ON r.ManagerID = m.ManagerID
            JOIN Products pr ON r.ProductID = pr.ProductID
            WHERE r.PartnerID = %s
        """, (partner_id,))
        requests = cursor.fetchall()
        logger.info(f"Найдено заявок для партнёра {partner_id}: {len(requests)}")
        
        cursor.close()
        conn.close()
        return render_template('partner_requests.html', requests=requests, partner_name=partner_name)
    except Exception as e:
        logger.error(f"Ошибка в /partner_requests/{partner_id}: {str(e)}")
        return render_template('error.html', error=f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Requests.")