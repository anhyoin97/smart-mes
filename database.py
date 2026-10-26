import sqlite3


DB_PATH = "mes.db"


def get_db_connection():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn

def init_db():

    # schema
    with open("schema.sql", "r", encoding="utf-8") as file:
        
        schema = file.read()

    # seed_data
    with open("seed_data.sql", "r", encoding="utf-8") as file:
        seed_data = file.read()

    # sensor_seed_data
    with open("sensor_seed_data.sql", "r", encoding="utf-8") as file:
        sensor_seed_data = file.read()

    conn = get_db_connection()

    conn.executescript(schema)
    conn.executescript(seed_data)
    conn.executescript(sensor_seed_data)

    conn.commit()

    conn.close()

if __name__ == "__main__":

    init_db()

    print("MES Database 생성 완료")