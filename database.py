import sqlite3


DB_PATH = "mes.db"


def get_db_connection():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn

def init_db():

    with open("schema.sql", "r", encoding="utf-8") as file:
        
        schema = file.read()

    conn = get_db_connection()

    conn.executescript(schema)

    conn.commit()

    conn.close()

if __name__ == "__main__":

    init_db()

    print("MES Database 생성 완료")