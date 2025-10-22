from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import role_required
from db import get_db_connection
import csv
import io
import re
import logging

upload_bp = Blueprint('upload', __name__)
logger = logging.getLogger(__name__)

@upload_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def upload():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash("Файл не выбран", "error")
            return redirect(url_for('upload.upload'))
        
        file = request.files['csv_file']
        if not file.filename.endswith('.csv'):
            flash("Файл должен быть в формате CSV", "error")
            return redirect(url_for('upload.upload'))
        
        try:
            stream = io.StringIO(file.stream.read().decode("utf-8"))
            csv_reader = csv.DictReader(stream)
            expected_columns = {'Name', 'LegalAddress', 'INN', 'DirectorFullName', 'Phone', 'Email', 'Rating'}
            
            if not expected_columns.issubset(csv_reader.fieldnames):
                flash("Неверный формат CSV. Ожидаемые столбцы: Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating", "error")
                return redirect(url_for('upload.upload'))
            
            conn, db_status = get_db_connection()
            if not conn:
                flash(db_status["message"], "error")
                return redirect(url_for('upload.upload'))
            
            cursor = conn.cursor()
            inserted = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):
                name = row['Name'].strip()
                legal_address = row['LegalAddress'].strip() or None
                inn = row['INN'].strip() or None
                director_full_name = row['DirectorFullName'].strip() or None
                phone = row['Phone'].strip() or None
                email = row['Email'].strip() or None
                rating = row['Rating'].strip() or None

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
            return redirect(url_for('upload.upload'))
        
        except Exception as e:
            flash(f"Ошибка обработки файла: {str(e)}", "error")
            return redirect(url_for('upload.upload'))
    
    return render_template('upload.html')