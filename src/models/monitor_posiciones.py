import os
import sys
import logging
import importlib.util
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf
from pydantic import BaseModel, field_validator
from typing import List

# Fix for windows encoding issues with emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import sys
import os

# Agregar la ruta base del operador para importar sus modulos
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
OPERADOR_DIR = os.path.join(ROOT_DIR, 'operador_tendencia_alcista')
sys.path.insert(0, OPERADOR_DIR)
from src.estructura.cotas_historicas import DetectorCotas
sys.path.pop(0)

# Importar lógica Domenec desde archivo local
script_path = os.path.join(ROOT_DIR, 'src', 'models', 'script deteccion momentum domenec.py')
spec = importlib.util.spec_from_file_location("domenec", script_path)
domenec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domenec)
apply_indicators = domenec.apply_indicators

# ARTÍCULO 5: LOGGING CIENTÍFICO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('MonitorCartera')

# Paths principales
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
CARTERA_PATH = os.path.join(ROOT_DIR, 'data/raw/cartera_activa.csv')

# ARTÍCULO 3: VALIDACIÓN DE DATOS CON PYDANTIC
class Posicion(BaseModel):
    """Esquema de validación para una posición de la cartera."""
    Ticker: str
    Fecha_Compra: str
    Cantidad: int
    Precio_Compra: float
    
    @field_validator('Cantidad')
    def validar_cantidad(cls, v):
        if v <= 0:
            raise ValueError(f"La cantidad debe ser mayor a 0, recibida: {v}")
        return v
        
    @field_validator('Precio_Compra')
    def validar_precio(cls, v):
        if v <= 0.0:
            raise ValueError(f"El precio debe ser positivo, recibido: {v}")
        return v

class CarteraModel(BaseModel):
    """Esquema de validación general para todas las posiciones."""
    posiciones: List[Posicion]

# ARTÍCULO 2 y 8: FUNDAMENTO CIENTÍFICO Y DOCUMENTACIÓN
def evaluar_salida_domenec(df: pd.DataFrame) -> tuple:
    """
    Evalúa las condiciones de salida estructural de Domenec.
    
    Fundamento teórico:
        Método Domenec (Cuadernos NotebookLM "Analisis técnico Domenec").
        Salida dinámica temporalizada a favor del seguimiento de tendencia.
    
    Reglas de Salida:
        1. Cierre diario por debajo de la Genial Line (SMA 34) -> Salida Inmediata.
        2. 2 Cierres consecutivos diarios por debajo de la Zona de Corrección 
           (menor a EMA 8 y Wilder 8).
    
    Args:
        df: DataFrame procesado con apply_indicators (debe contener Genial_Line, EMA_8, Wilder_8).
        
    Returns:
        tuple: (booleano_salida, razon_salida)
    """
    if len(df) < 2:
        return False, "Datos insuficientes"
        
    # Ultima vela (T) y penúltima (T-1)
    vela_t = df.iloc[-1]
    vela_t1 = df.iloc[-2]
    
    # Condición 1: Quiebre de Genial Line
    if vela_t['Close'] < vela_t['Genial_Line']:
        return True, "🔴 VENTA: Quiebre bajista de Genial Line (SMA 34)"
        
    # Condición 2: Dos velas consecutivas por debajo de Zona de Corrección
    limite_inf_t = min(vela_t['EMA_8'], vela_t['Wilder_8'])
    limite_inf_t1 = min(vela_t1['EMA_8'], vela_t1['Wilder_8'])
    
    fuera_t = vela_t['Close'] < limite_inf_t
    fuera_t1 = vela_t1['Close'] < limite_inf_t1
    
    if fuera_t and fuera_t1:
        return True, "🔴 VENTA: 2 velas consecutivas debajo de Zona de Corrección"
        
    return False, "🛡️  MANTENER POSICIÓN"

def comprobar_costo_oportunidad(ticker: str, tickers_cartera: list, current_price: float, df_diario: pd.DataFrame, estado_control: str) -> tuple:
    """
    Comprueba si existe un nuevo activo con mayor probabilidad estadística (Ranking).
    Se sugiere la rotación SI Y SÓLO SI:
    1. El activo cayó excesivamente de su "Zona Segura" (Top 8).
    O:
    2. El activo en cartera está CERCANO (<5%) a un Techo/Resistencia (Trimestral/Semanal)
       Y está Perdiendo Fuerza de momentum.
    """
    ranking_path = os.path.join(ROOT_DIR, 'data/processed/Ranking_Argentina_Top.xlsx')
    if not os.path.exists(ranking_path):
        return False, "Ranking no disponible"
        
    df_rank = pd.read_excel(ranking_path)
    if 'Ticker' not in df_rank.columns:
        return False, "Formato de ranking inválido"
        
    zona_segura = df_rank['Ticker'].head(8).tolist()
    top5_tickers = df_rank['Ticker'].head(5).tolist()
    
    # Evaluar Cotas
    df_sem = df_diario.resample('W').last().dropna()
    df_trim = df_diario.resample('Q').last().dropna()
    datos_mt = {'diario': df_diario, 'semanal': df_sem, 'trimestral': df_trim}
    
    cotas = DetectorCotas().detectar(datos_mt)
    resistencia_peligrosa = False
    distancia_pct = 999.0
    cota_jerarquia = ""
    
    if cotas:
        cotas_superiores = sorted([c for c in cotas if c.precio > current_price], key=lambda x: x.precio)
        if cotas_superiores:
            cota_cercana = cotas_superiores[0]
            distancia_pct = (cota_cercana.precio / current_price) - 1
            # Peligro si estamos a menos de 5% de un techo Trimestral o Semanal
            if cota_cercana.jerarquia in ['Trimestral', 'Semanal'] and distancia_pct < 0.05:
                resistencia_peligrosa = True
                cota_jerarquia = cota_cercana.jerarquia
    
    perdiendo_fuerza = any(x in estado_control for x in ["Amarillo", "Rojo", "Bajista", "Correccion", "BrownDark", "Purple"])

    # Evitar concentración: buscar alternativas que NO tenga actualmente en cartera
    candidatos_nuevos = [t for t in top5_tickers if t not in tickers_cartera]
    alternativa = candidatos_nuevos[0] if candidatos_nuevos else "N/A"
    
    if alternativa == "N/A":
        alternativas_ranking = [t for t in df_rank['Ticker'].tolist() if t not in tickers_cartera]
        alternativa = alternativas_ranking[0] if alternativas_ranking else "N/A"
    
    if alternativa != "N/A":
        # Condición 1: Cayó estructuralmente del Top
        if ticker not in zona_segura:
            return True, f"⚠️ ROTAR: Cayó del Top 8. Intercambiar por {alternativa}."
            
        # Condición 2: Resistencia Macro cerca + Pérdida de Fuerza
        if resistencia_peligrosa and perdiendo_fuerza:
            return True, f"⚠️ ROTAR: Cerca de Techo {cota_jerarquia} (+{distancia_pct:.1%}) y perdiendo momentum. Sugerido: {alternativa}."

    return False, "Mantener con fundamentos intactos y sin bloqueos macro"

def monitorear_cartera():
    """Ejecuta el ciclo principal de screening post-compra."""
    
    # 1. Cargar archivo crudo e inmutable
    if not os.path.exists(CARTERA_PATH):
        logger.error(f"No se encontró el archivo de cartera en: {CARTERA_PATH}")
        return

    df_raw = pd.read_csv(CARTERA_PATH)
    
    # 2. Validación de datos estricta
    posiciones_list = []
    for _, row in df_raw.iterrows():
        try:
            pos = Posicion(
                Ticker=row['Ticker'],
                Fecha_Compra=row['Fecha_Compra'],
                Cantidad=int(row['Cantidad']),
                Precio_Compra=float(row['Precio_Compra'])
            )
            posiciones_list.append(pos)
        except Exception as e:
            logger.error(f"Fallo de validación en fila: {row.to_dict()} - Error: {e}")
            continue
            
    try:
        CarteraModel(posiciones=posiciones_list)
        logger.info(f"Supuestos y datos validados: {len(posiciones_list)} activos correctamente esquematizados.")
    except Exception as e:
        logger.critical(f"La cartera entera no pasa validación estructural: {e}")
        return

    print("\n=========================================================================================")
    print("📡  SISTEMA DE MONITOREO CUANTITATIVO DE CARTERA (MÉTODO DOMENEC)")
    print("=========================================================================================")
    
    total_invertido = 0.0
    total_mercado = 0.0

    print(f"  {'TICKER':<10} {'COMPRA':>8} {'ACTUAL':>8} {'RENDIMIENTO':>13}  {'ESTADO DOMENEC / ROTACIÓN'}")
    print("-" * 89)

    # Extraer la lista simple de tickers actuales en la cartera para pasarlo al filtro anti-concentración
    tickers_actuales = [p.Ticker for p in posiciones_list]

    for p in posiciones_list:
        try:
            # Descargar historial (período largo para nutrir la SMA 34 de Domenec)
            hist = yf.download(p.Ticker, period="6mo", progress=False, auto_adjust=True)
            if hist.empty:
                logger.warning(f"No se obtuvieron datos para {p.Ticker}")
                continue
                
            if isinstance(hist.columns, pd.MultiIndex):
                hist = hist.xs(p.Ticker, level='Ticker', axis=1)

            # Aplicar indicadores del Túnel Domenec y Control
            hist = apply_indicators(hist)
            if hist.empty or 'Genial_Line' not in hist.columns:
                logger.error(f"Falla en cálculo de indicadores Domenec para {p.Ticker}")
                continue

            current_price = hist['Close'].iloc[-1]
            
            # Evaluación Técnica de Salida Domenec
            salida_requerida, razon_estado = evaluar_salida_domenec(hist)
            
            # Evaluación Costo de Oportunidad (Rotación) si está perdiendo fuerza / bloqueado
            estado_control_actual = hist['Status_Control'].iloc[-1]
            rotar, razon_rotacion = comprobar_costo_oportunidad(
                p.Ticker, 
                tickers_actuales, 
                current_price, 
                hist, 
                estado_control_actual
            )
            
            # Si debemos vender por estructura de riesgo absoluta (SL), no importa rotar, hay que liquidar ya
            if salida_requerida:
                estado_final = razon_estado
            elif rotar:
                estado_final = razon_rotacion
            else:
                estado_final = f"{razon_estado} ({estado_control_actual})"
            
            # Cálculo patrimonial
            inv_inicial = p.Cantidad * p.Precio_Compra
            patrimonio_actual = p.Cantidad * current_price
            rendimiento_pct = (current_price / p.Precio_Compra) - 1
            
            total_invertido += inv_inicial
            total_mercado += patrimonio_actual
                
            rend_str = f"{rendimiento_pct:+.2%}"
            print(f"  {p.Ticker:<10} ${p.Precio_Compra:>7.2f} ${float(current_price):>7.2f} {rend_str:>13}  {estado_final}")

        except Exception as e:
            logger.error(f"Falla estructural para {p.Ticker}: {e}")
            
    pnl_total = (total_mercado / total_invertido) - 1 if total_invertido > 0 else 0
    print("-" * 89)
    print(f"\n  Capital Inicial: ${total_invertido:,.2f}")
    print(f"  Patrimonio Actual: ${total_mercado:,.2f}")
    print(f"  PNL Acumulado (Abierto): {pnl_total:+.2%}")
    print("=========================================================================================\n")
    logger.info("Monitoreo Domenec ejecutado existosamente, fundamentos teóricos y cruces respetados.")
    
if __name__ == "__main__":
    monitorear_cartera()
