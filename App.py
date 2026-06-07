import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Trading Plan Pro + Candle Signal", page_icon="📈", layout="wide")

# Gaya CSS Tema Gelap Elegan
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .stMetric { background-color: #1f2937; padding: 10px; border-radius: 10px; border: 1px solid #374151; }
    h3 { color: #10B981; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 DASHBOARD TRADING PLAN & SINYAL CANDLESTICK")
st.write(f"Analisis Otomatis Candlestick Reversal — Pembaruan Terakhir: {date.today().strftime('%d %B %Y')}")

ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BRMS").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Menganalisis pergerakan lilin (candlestick)...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date)
        
    if not data_saham.empty:
        # Normalisasi struktur kolom yfinance jika berbentuk Multi-Index
        if isinstance(data_saham.columns, pd.MultiIndex):
            data_saham.columns = data_saham.columns.get_level_values(0)
            
        # Memastikan data berupa deret data tunggal (Series)
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if isinstance(data_saham[col], pd.DataFrame):
                data_saham[col] = data_saham[col].iloc[:, 0]

        # Ambil nilai array harga
        open_arr = data_saham['Open'].values
        high_arr = data_saham['High'].values
        low_arr = data_saham['Low'].values
        close_arr = data_saham['Close'].values
        volume_arr = data_saham['Volume'].values

        harga_terakhir = float(close_arr[-1])
        harga_sebelumnya = float(close_arr[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100

        # --- LOGIKA DETEKSI 5 POLA BULLISH CANDLESTICK ---
        pola_terdeteksi = []
        
        if len(close_arr) >= 4:
            # Komponen Candle Terakhir (-1)
            body_1 = abs(close_arr[-1] - open_arr[-1])
            range_1 = high_arr[-1] - low_arr[-1] if (high_arr[-1] - low_arr[-1]) > 0 else 1
            bull_1 = close_arr[-1] > open_arr[-1]
            bear_1 = close_arr[-1] < open_arr[-1]
            ushadow_1 = high_arr[-1] - max(open_arr[-1], close_arr[-1])
            lshadow_1 = min(open_arr[-1], close_arr[-1]) - low_arr[-1]
            
            # Komponen Candle Dua Hari Lalu (-2)
            body_2 = abs(close_arr[-2] - open_arr[-2])
            bear_2 = close_arr[-2] < open_arr[-2]
            bull_2 = close_arr[-2] > open_arr[-2]
            
            # Komponen Candle Tiga Hari Lalu (-3)
            body_3 = abs(close_arr[-3] - open_arr[-3])
            bear_3 = close_arr[-3] < open_arr[-3]
            bull_3 = close_arr[-3] > open_arr[-3]

            # 1. HAMMER: Ekor bawah panjang (min 2x body), ekor atas sangat kecil
            if lshadow_1 >= 2 * body_1 and ushadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("🔨 Hammer (Pembalikan Arah Naik)")

            # 2. BULLISH ENGULFING: Candle hijau saat ini memakan habis seluruh badan candle merah kemarin
            if bear_2 and bull_1 and close_arr[-1] >= open_arr[-2] and open_arr[-1] <= close_arr[-2]:
                pola_terdeteksi.append("🔥 Bullish Engulfing (Tekanan Beli Kuat)")

            # 3. MORNING STAR: Formasi 3 candle (Merah panjang -> Doji/Candle kecil bawah -> Hijau panjang)
            if bear_3 and body_2 < 0.3 * body_3 and bull_1 and close_arr[-1] > (open_arr[-3] + close_arr[-3])/2:
                pola_terdeteksi.append("🌅 Morning Star (Sinyal Dasar Reversal Kuat)")

            # 4. THREE WHITE SOLDIERS: Tiga candle hijau beruntun dengan tangga naik konstan
            if bull_3 and bull_2 and bull_1 and close_arr[-1] > close_arr[-2] > close_arr[-3]:
                pola_terdeteksi.append("⚔️ Three White Soldiers (Konfirmasi Uptrend)")

            # 5. INVERTED HAMMER: Ekor atas panjang (min 2x body), ekor bawah sangat kecil di dasar tren
            if ushadow_1 >= 2 * body_1 and lshadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("📐 Inverted Hammer (Awal Dorongan Akumulasi)")

        # Perhitungan Indikator Tambahan untuk Statistik Dashboard
        data_saham['MA50'] = data_saham['Close'].rolling(window=50).mean()
        ma50_sekarang = float(data_saham['MA50'].iloc[-1])
        data_saham['Vol_Avg'] = data_saham['Volume'].rolling(window=20).mean()
        vol_avg = float(data_saham['Vol_Avg'].iloc[-1])

        # Perhitungan Support & Resistance Otomatis
        data_1w = data_saham.tail(5)
        h_1w = float(data_1w['High'].max())
        l_1w = float(data_1w['Low'].min())
        c_1w = float(data_1w['Close'].iloc[-1])
        pivot = (h_1w + l_1w + c_1w) / 3
        r1, r2 = (2 * pivot) - l_1w, pivot + (h_1w - l_1w)
        s1, s2 = (2 * pivot) - h_1w, pivot - (h_1w - l_1w)

        # Matriks Atas Dashboard
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN SAHAM", f"{ticker_input}.JK")
        col_m2.metric("HARGA SAAT INI", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME PASAR", f"{volume_arr[-1]/1e6:.1f} M", f"Rata-rata 20H: {vol_avg/1e6:.1f} M", delta_color="off")

        st.markdown("---")

        # Pembagian Layout Data & Grafis Candlestick
        col_data, col_chart = st.columns([1, 1.2])

        with col_data:
            # --- BLOK BARU: PANEL SINYAL UTAMA CANDLESTICK ---
            st.subheader("🔮 KANAL SINYAL CANDLESTICK (NEXT CANDLE)")
            if pola_terdeteksi:
                for pola in pola_terdeteksi:
                    st.success(f"**Pola Terdeteksi:** {pola}")
                st.markdown("""
                    <div style='background-color:#10B981; padding:12px; border-radius:8px; text-align:center;'>
                        <h3 style='color:white; margin:0;'>🚀 SIGNAL: BUY (UNTUK NEXT CANDLE)</h3>
                        <p style='color:white; margin:4px 0 0 0;'>Pola konfirmasi kenaikan divalidasi bursa.</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("⚪ **Sinyal:** Belum ada pola pembentukan 5 Bullish Candlestick utama pada candle terakhir. Ambil keputusan berdasarkan area batas support.")

            st.write("---")
            st.subheader("🎯 SETUP AREA TRADING")
            st.info(f"**BUY AREA:** Rp {int(s1):,.0f} - Rp {int(harga_terakhir):,.0f}")
            st.error(f"**STOP LOSS (SL):** Rp {int(s2 * 0.99):,.0f}")
            st.success(f"**TARGET AMBIL UNTUNG:** TP1: Rp {int(r1):,.0f} | TP2: Rp {int(r1*1.02):,.0f} | TP3: Rp {int(r2):,.0f}")

        with col_chart:
            st.write("### 📊 GRAFIK KANDIL (CANDLESTICK) REAL-TIME")
            # Grafik Candlestick Interaktif Plotly
            df_g = data_saham.tail(40)
            fig = go.Figure(data=[go.Candlestick(
                x=df_g.index, open=df_g['Open'], high=df_g['High'],
                low=df_g['Low'], close=df_g['Close'], name='Harga Saham'
            )])
            fig.add_trace(go.Scatter(x=df_g.index, y=df_g['MA50'], mode='lines', name='MA50 Trend Line', line=dict(color='#F59E0B', width=1.5)))
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=380)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Data emiten tidak berhasil ditarik dari server bursa.")
except Exception as e:
    st.error(f"Sistem gagal merelasikan data: {str(e)}")
