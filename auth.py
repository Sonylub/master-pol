from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
import bcrypt
from db import get_db_connection
from models import User
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
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
        try:
            cursor.execute("SELECT UserID, Username, Email, Password, Role, PartnerID FROM Users WHERE Username = %s", (username,))
            user = cursor.fetchone()
            if user and bcrypt.checkpw(password, user[3].encode('utf-8')):
                login_user(User(user[0], user[1], user[2], user[4], user[5]))
                flash("Вход выполнен успешно!", "success")
                return redirect(url_for('index'))
            flash("Неверное имя пользователя или пароль", "error")
        except Exception as e:
            logger.error(f"Ошибка при входе: {str(e)}")
            flash(f"Ошибка: {str(e)}", "error")
        finally:
            cursor.close()
            conn.close()
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    conn, db_status = get_db_connection()
    partners = []
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT PartnerID, Name FROM Partners")
            partners = cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка при получении списка партнёров: {str(e)}")
            flash(f"Ошибка: {str(e)}", "error")
        finally:
            cursor.close()
            conn.close()
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        role = request.form.get('role', 'partner')
        partner_id = request.form.get('partner_id') or None
        if role == 'partner' and not partner_id:
            flash("Для роли 'partner' необходимо выбрать партнёра", "error")
            return render_template('register.html', partners=partners)
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status["message"], "error")
            return render_template('register.html', partners=partners)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO Users (Username, Email, Password, Role, PartnerID) VALUES (%s, %s, %s, %s, %s)",
                (username, email, hashed_password, role, partner_id)
            )
            conn.commit()
            flash("Регистрация успешна! Войдите в систему.", "success")
            return redirect(url_for('auth.login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Имя пользователя или email уже заняты", "error")
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при регистрации: {str(e)}")
            flash(f"Ошибка: {str(e)}", "error")
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html', partners=partners)

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash("Вы вышли из системы", "success")
    return redirect(url_for('index'))