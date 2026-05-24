import sqlite3

conn = sqlite3.connect('new_database.db')
conn.execute('''
    CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        object_id INTEGER,
        filename TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
conn.close()
print("Таблицю photos успішно створено!")