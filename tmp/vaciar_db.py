import os
import sys

# Configurar path para importar desde src
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(ROOT_DIR)

from src.data.db_manager import DBManager

def vaciar_base():
    db_path = 'data/market_data.duckdb'
    if os.path.exists(db_path):
        print(f"Iniciando vaciado de base de datos: {db_path}")
        db = DBManager(db_path=db_path)
        db.clear_table('all')
        db.close()
        print("Base de datos vaciada exitosamente.")
    else:
        print(f"❓ No se encontró la base de datos en {db_path}. No hay nada que vaciar.")

if __name__ == "__main__":
    vaciar_base()
