import matplotlib.pyplot as plt
import pandas as pd
from typing import List
from ..estructura.cotas_historicas import Cota

class VisualizadorCotas:
    """
    Genera gráficos estáticos para visualizar Cotas Históricas.
    """
    
    @staticmethod
    def plot_cotas(df: pd.DataFrame, cotas: List[Cota], ticker: str):
        """
        Grafica velas japonesas, indicadores y cotas en escala logarítmica.
        """
        # Configuración de estilo
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(16, 9))
        
        # 1. Velas Japonesas (Manual sin mplfinance)
        # Separar alcistas y bajistas
        df = df.copy()
        df['Date'] = pd.to_datetime(df.index)
        # Mapear fechas a indices numericos para evitar huecos de fines de semana
        df = df.reset_index(drop=True)
        
        # Configurar colores de velas según Status_Control de Domenec si existe
        if 'Status_Control' in df.columns:
            import numpy as np
            color_map = {
                'Cruce Bajista (Magenta)': '#FF00FF',
                'Cruce Alcista (Azul Profundo)': '#0046C8',
                'Correccion Fuerte (Rojo)': '#FF0000',
                'Sin Fuerza (Amarillo)': '#FFFA00',
                'Pullback (Azul)': '#1EB4E6',
                'Impulso Fuerte (Verde Osc)': '#466446',
                'Impulso Medio (Verde)': '#00FF00',
                'Pullback Bajista (Cian)': '#00FFFF',
                'Bajista Sin Fuerza (Naranja)': '#FA8C00',
                'Bajista Fuerte (Marron Oscuro)': '#642832',
                'Fuerza Bajista Media (Morado)': '#783C5A',
                'Reinicio Bajista (Marron Naranja)': '#783C14',
                'Neutral': '#808080'
            }
            # Mapear, usar gris por defecto si no coincide
            df['candle_color'] = df['Status_Control'].map(color_map).fillna('#808080')
        else:
            # Colores por defecto TradingView
            import numpy as np
            df['candle_color'] = np.where(df['Close'] >= df['Open'], '#26a69a', '#ef5350')
            
        up = df[df['Close'] >= df['Open']]
        down = df[df['Close'] < df['Open']]
        
        width = 0.6
        width2 = 0.05
        
        # Velas Alcistas
        ax.bar(up.index, up['Close'] - up['Open'], width, bottom=up['Open'], color=up['candle_color'], edgecolor=up['candle_color'])
        ax.bar(up.index, up['High'] - up['Close'], width2, bottom=up['Close'], color=up['candle_color'], edgecolor=up['candle_color'])
        ax.bar(up.index, up['Low'] - up['Open'], width2, bottom=up['Open'], color=up['candle_color'], edgecolor=up['candle_color'])
        
        # Velas Bajistas
        ax.bar(down.index, down['Open'] - down['Close'], width, bottom=down['Close'], color=down['candle_color'], edgecolor=down['candle_color'])
        ax.bar(down.index, down['High'] - down['Open'], width2, bottom=down['Open'], color=down['candle_color'], edgecolor=down['candle_color'])
        ax.bar(down.index, down['Low'] - down['Close'], width2, bottom=down['Close'], color=down['candle_color'], edgecolor=down['candle_color'])
        
        # 2. Indicadores (Si existen en el DF)
        
        # --- Tunel Domenec ---
        if 'EMA_123' in df.columns and 'EMA_188' in df.columns:
            ax.plot(df.index, df['EMA_123'], color='blue', linewidth=1)
            ax.plot(df.index, df['EMA_188'], color='blue', linewidth=1)
            ax.fill_between(df.index, df['EMA_123'], df['EMA_188'], color='blue', alpha=0.25)
            
        if 'EMA_416' in df.columns and 'EMA_618' in df.columns:
            ax.plot(df.index, df['EMA_416'], color='yellow', linewidth=1)
            ax.plot(df.index, df['EMA_618'], color='yellow', linewidth=1)
            ax.fill_between(df.index, df['EMA_416'], df['EMA_618'], color='yellow', alpha=0.25)
            
        if 'EMA_882' in df.columns and 'EMA_1223' in df.columns:
            ax.plot(df.index, df['EMA_882'], color='#FF1493', linewidth=1)
            ax.plot(df.index, df['EMA_1223'], color='#FF1493', linewidth=1)
            ax.fill_between(df.index, df['EMA_882'], df['EMA_1223'], color='#FF1493', alpha=0.25)

        # --- Zona de Corrección ---
        if 'EMA_8' in df.columns and 'Wilder_8' in df.columns:
            ax.plot(df.index, df['EMA_8'], color='white', linewidth=1, alpha=0.5)
            ax.plot(df.index, df['Wilder_8'], color='#853805', linewidth=2, label='Wilder 8')
            
            # Fill between condicional
            ax.fill_between(df.index, df['EMA_8'], df['Wilder_8'], 
                            where=(df['EMA_8'] > df['Wilder_8']), 
                            color='green', alpha=0.25)
            ax.fill_between(df.index, df['EMA_8'], df['Wilder_8'], 
                            where=(df['EMA_8'] <= df['Wilder_8']), 
                            color='red', alpha=0.25)

        # --- Genial Line ---
        if 'Genial_Line' in df.columns:
            ax.plot(df.index, df['Genial_Line'], color='white', marker='+', linestyle='None', 
                    markersize=4, label='Genial Line (SMA 34)')

        # 3. Cotas Históricas
        # Mapa de colores y estilos acelerados
        estilos_cotas = {
            'Trimestral': {'color': '#0000FF', 'ls': '-', 'lw': 2.5, 'alpha': 0.9},
            'Mensual':    {'color': '#1E88E5', 'ls': '-', 'lw': 2.0, 'alpha': 0.8},
            'Semanal':    {'color': '#FF9800', 'ls': '--', 'lw': 1.5, 'alpha': 0.9},
            'Diaria':     {'color': '#D50000', 'ls': ':', 'lw': 1.0, 'alpha': 0.6}
        }

        # Calcular limites de visualizacion (percentiles para ignorar outliers)
        # Importante para grafica LOG: Evitar valores cercanos a 0 que estiran el eje.
        if not df.empty:
            min_p = df['Low'].quantile(0.01) * 0.9
            max_p = df['High'].quantile(0.99) * 1.1
            # Asegurar minimo razonable para log (ej: 0.1)
            min_view = max(0.1, min_p)
            ax.set_ylim(bottom=min_view, top=max_p)
        else:
            min_view, max_p = 0.1, 100

        # Dibujar cotas (Solo las visibles en el rango actual)
        processed_prices = []
        for cota in cotas:
            # Filtrar estrictamente por rango visual
            if not (min_view <= cota.precio <= max_p):
                continue
                
            conf = estilos_cotas.get(cota.jerarquia, estilos_cotas['Diaria'])
            ax.axhline(y=cota.precio, color=conf['color'], linestyle=conf['ls'], 
                       linewidth=conf['lw'], alpha=conf['alpha'])
            
            # Texto
            too_close = any(abs(cota.precio - p) / p < 0.05 for p in processed_prices)
            if not too_close:
                # Pegar texto a la derecha, pero dentro del rango X
                x_pos = df.index[-1]
                ax.text(x_pos, cota.precio, f" {cota.jerarquia} {cota.precio:.2f}", 
                        color=conf['color'], verticalalignment='center', fontsize=9, fontweight='bold')
                processed_prices.append(cota.precio)

        from matplotlib.ticker import ScalarFormatter
        
        # 4. Configuración Final
        ax.set_yscale('log')
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.set_title(f"Análisis Cotas Históricas {ticker} [Log] - Velas Diarias (10 Años)", fontsize=14, color='white')
            
        ax.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.grid(True, which='minor', linestyle=':', linewidth=0.3, alpha=0.2)
        
        # Formatear Eje X
        step = max(1, len(df) // 10)
        ax.set_xticks(df.index[::step])
        ax.set_xticklabels(df['Date'].dt.strftime('%Y-%m-%d').iloc[::step], rotation=45, ha='right')
        
        # Leyenda compacta
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc='upper left', facecolor='black', framealpha=0.5, fontsize=8)
            
        plt.tight_layout()
        plt.show()
