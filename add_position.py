import sqlite3

conn = sqlite3.connect('new_database.db')
try:
    conn.execute('ALTER TABLE objects ADD COLUMN position INTEGER DEFAULT 0')
    print("Колонку для сортування успішно додано!")
except Exception as e:
    print("Помилка (можливо колонка вже існує):", e)
conn.commit()
conn.close()