import sqlite3
from config.settings import DATABASE_PATH


def create_database():

    conn = sqlite3.connect(DATABASE_PATH)

    cursor = conn.cursor()


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT,
        speed REAL,
        status TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)


    conn.commit()
    conn.close()



def save_vehicle(plate, speed, status):

    conn = sqlite3.connect(DATABASE_PATH)

    cursor = conn.cursor()


    cursor.execute("""
    INSERT INTO vehicles
    (plate, speed, status)
    VALUES (?, ?, ?)
    """,
    (
        plate,
        speed,
        status
    ))


    conn.commit()
    conn.close()