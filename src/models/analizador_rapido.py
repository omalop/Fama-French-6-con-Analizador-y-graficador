import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

# Solución para imprimir Emojis en la terminal de Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuración de Paths
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(ROOT_DIR)

# Agregar la ruta base del operador para sus imports internos
OPERADOR_DIR = os.path.join(ROOT_DIR, 'operador_tendencia_alcista')
# Insertar primero para que la carpeta "src" en "operador_tendencia_alcista" tenga prioridad en imports del operador
sys.path.insert(0, OPERADOR_DIR)

from src.estructura.cotas_historicas import DetectorCotas
from src.visualizacion.grafico_cotas import VisualizadorCotas

# Remover la ruta del operador para no confundir al resto del proyecto
sys.path.pop(0)

# Importar Domenec
try:
    import importlib.util
    dom_path = os.path.join(ROOT_DIR, 'src', 'models', 'script deteccion momentum domenec.py')
    spec = importlib.util.spec_from_file_location("domenec", dom_path)
    domenec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(domenec)
    apply_indicators = domenec.apply_indicators
except Exception as e:
    print(f"Error cargando Domenec: {e}")
    apply_indicators = None


_ccl_cache = None

def get_ccl_factor():
    global _ccl_cache
    if _ccl_cache is not None:
        return _ccl_cache
    
    print("⏳ Descargando cotizaciones de GGAL para cálculo del dólar CCL...")
    df_ccl = yf.download(['GGAL.BA', 'GGAL'], period="10y", progress=False, auto_adjust=True)
    if isinstance(df_ccl.columns, pd.MultiIndex):
        if 'Close' in df_ccl.columns:
            closes = df_ccl['Close']
        elif 'Adj Close' in df_ccl.columns:
            closes = df_ccl['Adj Close']
        else:
            closes = df_ccl
    else:
        closes = df_ccl
    
    closes_aligned = closes[['GGAL.BA', 'GGAL']].dropna()
    ccl_factor = (closes_aligned['GGAL.BA'] * 10) / closes_aligned['GGAL']
    _ccl_cache = ccl_factor
    return ccl_factor

def analizar_ticker(ticker: str, graficar: bool = False):
    print(f"\n" + "="*80)
    print(f" 🔍 ANALIZADOR RÁPIDO COBINADO: {ticker.upper()}")
    print("="*80)
    
    # 1. OBTENER DATOS MULTITEMPORALES (Para Cotas)
    print("⏳ Descargando datos y procesando temporalidades...")
    try:
        # Descarga historia larga (max o últ 10 años)
        df_diario = yf.download(ticker, period="10y", progress=False, auto_adjust=True)
        if df_diario.empty:
            print(f"❌ No se pudieron obtener datos para {ticker}.")
            return
            
        if isinstance(df_diario.columns, pd.MultiIndex):
            df_diario = df_diario.xs(ticker, level='Ticker', axis=1)

        is_argentine = ticker.endswith('.BA')
        if is_argentine:
            print("💱 Activo argentino detectado. Convirtiendo cotización a Dólar CCL (GGAL)...")
            ccl_factor = get_ccl_factor()
            # Filtrar fechas comunes (donde operan ambos mercados) y evitar desarbitrajes
            df_diario = df_diario.reindex(ccl_factor.index).dropna()
            # Dolarizar columnas de precio
            for col in ['Open', 'High', 'Low', 'Close']:
                if col in df_diario:
                    df_diario[col] = df_diario[col] / ccl_factor.loc[df_diario.index]

        # Resampling para Cotas usando la misma lógica del Operador Tendencia
        df_semanal = df_diario.resample('W').last() # Frecuencia semanal
        df_trimestral = df_diario.resample('QE').last() # Frecuencia trimestral

        datos_mt = {
            'diario': df_diario.dropna(),
            'semanal': df_semanal.dropna(),
            'trimestral': df_trimestral.dropna()
        }
        
        current_price = df_diario['Close'].iloc[-1]
        
    except Exception as e:
        print(f"❌ Error al descargar datos: {e}")
        return

    # 2. DETECTAR COTAS HISTÓRICAS
    print("📐 Calculando Cotas Históricas (Trimestral/Semanal/Diario)...")
    detector = DetectorCotas()
    cotas = detector.detectar(datos_mt)
    
    # Filtrar y ordenar cotas
    cotas_ordenadas = sorted(cotas, key=lambda x: x.precio)
    
    # Encontrar cotas más cercanas (Soporte y Resistencia)
    cotas_superiores = [c for c in cotas_ordenadas if c.precio > current_price]
    cotas_inferiores = [c for c in reversed(cotas_ordenadas) if c.precio < current_price]
    
    # 3. APLICAR DOMENEC (Status de Corto Plazo)
    print("📊 Calculando Indicadores Túnel Domenec...")
    df_plot = df_diario.copy()
    if apply_indicators:
        df_domenec = apply_indicators(df_diario.copy())
        if not df_domenec.empty and 'Status_Control' in df_domenec.columns:
            estado_domenec = df_domenec['Status_Control'].iloc[-1]
            genial_line = df_domenec['Genial_Line'].iloc[-1]
            dist_genial = ((current_price / genial_line) - 1) * 100
            df_plot = df_domenec
        else:
            estado_domenec = "Indeterminado"
            dist_genial = 0
    else:
        estado_domenec = "No disponible"
        dist_genial = 0

    # 4. MOSTRAR RESULTADOS
    print("\n" + "-"*80)
    print(f" 📋 RESULTADOS PARA {ticker.upper()}")
    print("-"*80)
    print(f" 💵 Precio Actual:     $ {current_price:,.2f}")
    print(f" 📈 Estado Domenec:    {estado_domenec}")
    if estado_domenec not in ["Indeterminado", "No disponible"]:
        print(f" 📏 Distancia G-Line:  {dist_genial:+.2f}%  (Línea Genial: $ {genial_line:,.2f})")
    
    print("\n 🧱 ESTRUCTURA DE COTAS (SOPORTES Y RESISTENCIAS):")
    
    # Mostrar hasta 2 resistencias arriba
    if cotas_superiores:
        for i, c in enumerate(cotas_superiores[:2]):
            dist_pct = ((c.precio / current_price) - 1) * 100
            print(f"    🔼 Resistencia {i+1}:  $ {c.precio:>8,.2f}  (+{dist_pct:>5.1f}%)  [{c.jerarquia}]")
    else:
        print("    🔼 Resistencia:    (Máximos Históricos - Sin Cotas Arriba)")
        
    print(f"    ▶️ PRECIO ACTUAL:  $ {current_price:>8,.2f}")
    
    # Mostrar hasta 2 soportes abajo
    if cotas_inferiores:
        for i, c in enumerate(cotas_inferiores[:2]):
            dist_pct = ((c.precio / current_price) - 1) * 100
            print(f"    🔽 Soporte {i+1}:      $ {c.precio:>8,.2f}  ({dist_pct:>6.1f}%)  [{c.jerarquia}]")
    else:
        print("    🔽 Soporte:        (Mínimos Históricos - Sin Cotas Abajo)")

    print("-"*80)

    # 5. GRAFICAR (Si se solicita)
    if graficar:
        print("🎨 Generando gráfico visual de cotas y velas...")
        VisualizadorCotas.plot_cotas(df_plot, cotas, ticker)


def main():
    print("\n" + "="*80)
    print(" ⚡  ANALIZADOR RÁPIDO: COTAS HISTÓRICAS + DOMENEC  ⚡")
    print("="*80)
    
    if len(sys.argv) > 1:
        entrada = " ".join(sys.argv[1:])
        grafico = False
    else:
        print("Instrucciones: Ingrese uno o varios tickers separados por comas.")
        print("Ejemplos: ALUA.BA, GGAL.BA, YPF, SPY")
        
        entrada = input("\n👉 Ingrese Ticker/s: ").strip()
        if not entrada:
            print("Saliendo...")
            return
            
        grafico = input("👉 ¿Desea ver el gráfico para cada activo? (s/n): ").strip().lower() == 's'
    
    tickers = [t.strip().upper() for t in entrada.split(',')]
    
    for tk in tickers:
        analizar_ticker(tk, graficar=grafico)

if __name__ == '__main__':
    main()
