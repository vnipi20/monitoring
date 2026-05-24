import sqlite3 

def setup_database():
    conn = sqlite3.connect('new_database.db')
    c = conn.cursor()

    # Таблиця категорій
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                 )''')

    # Таблиця об'єктів (з прив'язкою до категорії)
    c.execute('''CREATE TABLE IF NOT EXISTS objects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    name TEXT,
                    company TEXT,
                    map_url TEXT,
                    FOREIGN KEY(category_id) REFERENCES categories(id)
                 )''')

    # Додаємо базові категорії для початку
    c.execute("INSERT INTO categories (name) VALUES ('LAMBDA'), ('NOVAK')")
    
    conn.commit()
    conn.close()
    print("Нова база даних успішно створена!")

if __name__ == '__main__':
    setup_database()