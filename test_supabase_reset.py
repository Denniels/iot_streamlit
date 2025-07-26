import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv('.env.local')

# Inicializa el cliente de Supabase
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase: Client = create_client(url, key)

def limpiar_sensor_data():
    print('Borrando todos los registros de sensor_data...')
    delete_response = supabase.table('sensor_data').delete().neq('id', 0).execute()
    print('Delete response:', delete_response)

    print('Intentando reiniciar el contador de autoincremento...')
    # Ejecuta el SQL para reiniciar el contador (requiere función RPC en Supabase)
    try:
        sql = "ALTER SEQUENCE sensor_data_id_seq RESTART WITH 1;"
        rpc_response = supabase.rpc('execute_sql', {'sql': sql}).execute()
        print('Sequence reset response:', rpc_response)
    except Exception as e:
        print('No se pudo reiniciar el contador automáticamente. Hazlo manualmente si es necesario.')
        print('Error:', e)

if __name__ == "__main__":
    limpiar_sensor_data()
    print('La tabla sensor_data está lista para recibir datos nuevos.')
