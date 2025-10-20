from flask import Flask, render_template
import pyodbc

app = Flask(__name__)

# Подключение к базе данных
def get_db_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=ADCLG1;"
        "DATABASE=PartnerManagement_01_MasterPol;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(conn_str)
        print("Подключение к базе успешно!")  # Для отладки
        return conn
    except Exception as e:
        print(f"Ошибка подключения: {str(e)}")  # Для отладки
        raise e

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/partners')
def partners():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT PartnerID, Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating
            FROM [PartnerManagement_01_MasterPol].[dbo].[Partners]
        """)
        partners = cursor.fetchall()
        print(f"Найдено партнёров: {len(partners)}")  # Для отладки
        for partner in partners:
            print(partner)  # Для отладки
        conn.close()
        return render_template('partners.html', partners=partners)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Partners."
        print(error_message)  # Для отладки
        return render_template('error.html', error=error_message)

if __name__ == '__main__':
    app.run(debug=True)