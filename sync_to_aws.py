import os
import time
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

LOCAL_DB = {
    'host': os.getenv('LOCAL_DB_HOST'),
    'port': os.getenv('LOCAL_DB_PORT'),
    'dbname': os.getenv('LOCAL_DB_NAME'),
    'user': os.getenv('LOCAL_DB_USER'),
    'password': os.getenv('LOCAL_DB_PASSWORD'),
}
AWS_DB = {
    'host': os.getenv('AWS_DB_HOST'),
    'port': os.getenv('AWS_DB_PORT'),
    'dbname': os.getenv('AWS_DB_NAME'),
    'user': os.getenv('AWS_DB_USER'),
    'password': os.getenv('AWS_DB_PASSWORD'),
}

SYNC_INTERVAL = 60  # segundos
SYNC_WINDOW = 120   # segundos (sincroniza últimos 2 minutos)

def get_local_data():
    conn = psycopg2.connect(**LOCAL_DB)
    cur = conn.cursor()
    since = datetime.utcnow() - timedelta(seconds=SYNC_WINDOW)
    cur.execute("""
        SELECT device_id, sensor_type, value, unit, raw_data, timestamp
        FROM sensor_data
        WHERE timestamp >= %s
        ORDER BY device_id, timestamp
    """, (since,))
    rows = cur.fetchall()
    conn.close()
    # Agrupar por dispositivo
    data = {}
    for r in rows:
        dev = r[0]
        if dev not in data:
            data[dev] = []
        data[dev].append({
            'sensor_type': r[1],
            'value': r[2],
            'unit': r[3],
            'raw_data': r[4],
            'timestamp': r[5].isoformat() if hasattr(r[5], 'isoformat') else str(r[5])
        })
    return data

def send_to_aws(data):
    conn = psycopg2.connect(**AWS_DB)
    cur = conn.cursor()
    for device_id, sensors in data.items():
        for s in sensors:
            cur.execute("""
                INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (device_id, sensor_type, timestamp) DO NOTHING;
            """, (
                device_id, s['sensor_type'], s['value'], s['unit'], s['raw_data'], s['timestamp']
            ))
    conn.commit()
    conn.close()

def main():
    while True:
        try:
            data = get_local_data()
            if data:
                send_to_aws(data)
            time.sleep(SYNC_INTERVAL)
        except Exception as e:
            print(f"Error en sincronización: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
