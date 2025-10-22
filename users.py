from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from db import get_db_connection
import bcrypt
import logging

users_bp = Blueprint('users', __name__)
logger = logging.getLogger(__name__)

@users_bp.route('/users')
@login_required
def users():
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    conn, db_status = get_db_connection()
    if not conn:
        return render_template('users.html', users=[], db_status=db_status)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT UserID, Username, Email, Role, PartnerID FROM Users")
        users = cursor.fetchall()
        return render_template('users.html', users=users, db_status=db_status)
    except Exception as e:
        logger.error(f"Ошибка при получении пользователей: {str(e)}")
        return render_template('users.html', users=[], db_status={'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@users_bp.route('/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'manager':
        logger.info(f"Доступ запрещён для пользователя {current_user.username} с ролью {current_user.role}")
        abort(403)
    username = request.form['username']
    email = request.form['email']
    password = request.form['password'].encode('utf-8')
    role = request.form.get('role', 'partner')
    partner_id = request.form.get('partner_id') or None
    if role == 'partner' and not partner_id:
        flash("Для роли 'partner' необходимо выбрать партнёра", "error")
        return redirect(url_for('index'))
    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
    conn, db_status = get_db_connection()
    if not conn:
        flash(db_status["message"], "error")
        return redirect(url_for('index'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Users (Username, Email, Password, Role, PartnerID) VALUES (%s, %s, %s, %s, %s)",
            (username, email, hashed_password, role, partner_id)
        )
        conn.commit()
        flash("Пользователь успешно добавлен", "success")
        return redirect(url_for('users.users'))
    except psycopg2.IntegrityError:
        conn.rollback()
        flash("Имя пользователя или email уже заняты", "error")
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка при добавлении пользователя: {str(e)}")
        flash(f"Ошибка: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index'))