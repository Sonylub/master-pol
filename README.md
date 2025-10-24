# Подсистема "Работа с партнерами"

## Ссылка на сайт
https://master-pol.vercel.app/

## Описание
Система автоматизирует управление партнёрами, заявками, поставками, материалами и продукцией для компании "Мастер пол" (напольные покрытия). Функции:
- Таблица партнёров (наименование, адрес, ИНН, директор, телефон, email, рейтинг).
- Добавление/редактирование партнёров.
- Заявки (продукция, количество, цена, статус, скидки).
- Поставки, материалы, продукция (остатки, состав).
- Импорт CSV.
- Расчёт материалов.
- Стили: Segoe UI, цвета #FFFFFF/#F4E8D3/#67BA80.
Поставка: проект, exe (PyInstaller), установщик (Inno Setup), документация.

## Требования
- **СУБД**: SQL Server (Express или выше).
- **ОС**: Windows.
- **Зависимости**: Python 3.11, `flask`, `pyodbc`, `pandas` (см. `requirements.txt`), ODBC Driver 17 for SQL Server.
- **Сеть**: Доступ к SQL Server в локальной сети учебного заведения (или VPN/локальный SQL Server Express).

## Файловая структура
```
master-pol/
├── static/
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   └── scripts.js
│   ├── images/
│   │   └── logo.png
├── templates/
│   ├── index.html
│   ├── partners.html
│   ├── partner_requests.html
│   ├── requests.html
│   ├── add_request.html
│   ├── supplies.html
│   ├── products.html
│   ├── materials.html
│   ├── upload.html
│   ├── calc.html
│   ├── login.html
│   ├── register.html
│   ├── error.html
├── .env
├── requirements.txt
├── app.py
├── config.py
├── auth.py
├── partners.py
├── requests.py
├── supplies.py
├── products.py
├── materials.py
├── upload.py
├── calc.py
├── db.py
├── models.py
```