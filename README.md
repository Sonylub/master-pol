# Подсистема "Работа с партнерами"

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
├── .venv/
├── app.py
├── requirements.txt
├── vercel.json
├── templates/
│   ├── index.html
│   ├── partners.html
│   ├── error.html
│   ├── add_partner.html
│   ├── add_request.html
│   ├── calc.html
│   ├── materials.html
│   ├── products.html
│   ├── requests.html
│   ├── supplies.html
│   ├── upload.html
├── static/
│   ├── css/styles.css
│   ├── images/logo.png
│   └── uploads/
├── sql/init.sql
├── docs/README.md
└── setup.py
```