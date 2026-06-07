import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Trading Plan Harian Pro", page_icon="📈", layout="wide")

# Gaya Tampilan Premium Bertema Gelap (Dark Mode)
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .stMetric { background-color: #1f2937; padding: 10px; border-radius: 10px; border: 1px solid #374151; }
    h3 { color: #10B981; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 DASHBOARD TRADING PLAN HARIAN (DAILY CLOSE)")
st.write(f"Analisis Pola Candlestick & Strategi Per Hari — Update: {date.today().strftime('%d %B %Y')}")

ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BRMS").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    # Mengambil data harian (interval='1d') secara eksplisit
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Membaca pergerakan candle harian...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date, interval="1d")
        
    if not data_saham.empty:
        # Normalisasi kolom jika format data bertingkat (Multi-Index)
        if isinstance(data_saham.columns, pd.MultiIndex):
            data_saham.columns = data_saham.columns.get_level_values(0)
            
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if isinstance(data_saham[col], pd.DataFrame):
                data_saham[col] = data_saham[col].iloc[:, 0]

        # Ekstrak data harga ke bentuk Array
        open_arr = data_saham['Open'].values
        high_arr = data_saham['High'].values
        low_arr = data_saham['Low'].values
        close_arr = data_saham['Close'].values
        volume_arr = data_saham['Volume'].values

        harga_terakhir = float(close_arr[-1])
        harga_sebelumnya = float(close_arr[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100

        # --- PEMBACAAN POLA CANDLESTICK HARIAN ---
        pola_terdeteksi = []
        
        if len(close_arr) >= 4:
            # Hitung komponen dasar Candle Hari Ini (-1)
            body_1 = abs(close_arr[-1] - open_arr[-1])
            range_1 = high_arr[-1] - low_arr[-1] if (high_arr[-1] - low_arr[-1]) > 0 else 1
            bull_1 = close_arr[-1] > open_arr[-1]
            bear_1 = close_arr[-1] < open_arr[-1]
            ushadow_1 = high_arr[-1] - max(open_arr[-1], close_arr[-1])
            lshadow_1 = min(open_arr[-1], close_arr[-1]) - low_arr[-1]
            
            # Hitung komponen dasar Candle Kemarin (-2)
            body_2 = abs(close_arr[-2] - open_arr[-2])
            bear_2 = close_arr[-2] < open_arr[-2]
            bull_2 = close_arr[-2] > open_arr[-2]
            
            # Hitung komponen dasar Candle 2 Hari Lalu (-3)
            body_3 = abs(close_arr[-3] - open_arr[-3])
            bear_3 = close_arr[-3] < open_arr[-3]
            bull_3 = close_arr[-3] > open_arr[-3]

            # 1. HAMMER
            if lshadow_1 >= 2 * body_1 and ushadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("🔨 Hammer (Sinyal Pembalikan Arah Naik)")

            # 2. BULLISH ENGULFING
            if bear_2 and bull_1 and close_arr[-1] >= open_arr[-2] and open_arr[-1] <= close_arr[-2]:
                pola_terdeteksi.append("🔥 Bullish Engulfing (Pembeli Mengambil Alih Pasar)")

            # 3. MORNING STAR
            if bear_3 and body_2 < 0.3 * body_3 and bull_1 and close_arr[-1] > (open_arr[-3] + close_arr[-3])/2:
                pola_terdeteksi.append("🌅 Morning Star (Formasi Bottom Reversal Kuat)")

            # 4. THREE WHITE SOLDIERS
            if bull_3 and bull_2 and bull_1 and close_arr[-1] > close_arr[-2] > close_arr[-3]:
                pola_terdeteksi.append("⚔️ Three White Soldiers (Konfirmasi Uptrend Harian)")

            # 5. INVERTED HAMMER
            if ushadow_1 >= 2 * body_1 and lshadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("📐 Inverted Hammer (Tekanan Beli Awal Mulai Masuk)")

        # Perhitungan MA50 & Volume Rata-rata
        data_saham['MA50'] = data_saham['Close'].rolling(window=50).mean()
        ma50_sekarang = float(data_saham['MA50'].iloc[-1])
        data_saham['Vol_Avg'] = data_saham['Volume'].rolling(window=20).mean()
        vol_avg = float(data_saham['Vol_Avg'].iloc[-1])

        # Hitung Pivot Support & Resistance Mingguan untuk jangkar harga harian
        data_1w = data_saham.tail(5)
        h_1w = float(data_1w['High'].max())
        l_1w = float(data_1w['Low'].min())
        c_1w = float(data_1w['Close'].iloc[-1])
        pivot = (h_1w + l_1w + c_1w) / 3
        r1, r2 = (2 * pivot) - l_1w, pivot + (h_1w - l_1w)
        s1, s2 = (2 * pivot) - h_1w, pivot - (h_1w - l_1w)

        # Nilai Trading Plan Otomatis
        buy_area_bawah, buy_area_atas = int(s1), int(harga_terakhir)
        stop_loss = int(s2 * 0.99)
        tp1, tp2 = int(r1), int(r1 * 1.03)

        # --- METRIKS UTAMA ATAS DASHBOARD ---
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN SAHAM", f"{ticker_input}.JK", "TIMEFRAME: HARIAN (1D)")
        col_m2.metric("HARGA CLOSE TERAKHIR", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME TRANSAKSI", f"{volume_arr[-1]/1e6:.1f} M", f"Rata-rata 20 Hari: {vol_avg/1e6:.1f} M", delta_color="off")

        st.markdown("---")

        # --- TAMPILAN DATA & GRAFIK CANDLE ---
        col_left, col_right = st.columns([1, 1.2])

        with col_left:
            st.subheader("🔮 PEMBACAAN CANDLE & SINYAL BESOK")
            if pola_terdeteksi:
                for pola in pola_terdeteksi:
                    st.success(f"**Pola Terdeteksi:** {pola}")
                st.markdown("""
                    <div style='background-color:#10B981; padding:15px; border-radius:8px; text-align:center;'>
                        <h3 style='color:white; margin:0;'>🚀 SIGNAL: BUY (UNTUK CANDLE BESOK)</h3>
                        <p style='color:white; margin:4px 0 0 0;'>Konfirmasi pola harian valid. Siap ambil posisi.</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("⚪ **Sinyal Harian:** Belum terbentuk 5 pola *Bullish Candlestick* utama pada penutupan hari ini. Pergerakan harga masih dalam range normal.")

            st.write("---")
            st.subheader("🏹 TRADING PLAN SETUP")
            st.info(f"🛒 **BUY AREA:** Rp {buy_area_bawah:,.0f} - Rp {buy_area_atas:,.0f}")
            st.error(f"⚠️ **STOP LOSS (SL):** Rp {stop_loss:,.0f}")
            st.success(f"🎯 **TARGET UTAMA (TP1 / TP2):** Rp {tp1:,.0f} / Rp {tp2:,.0f}")

        with col_right:
            st.subheader("📊 ANALISIS GRAFIK CANDLESTICK HARIAN")
            # Menampilkan 40 Candlestick Harian terakhir agar rapi di HP
            df_chart = data_saham.tail(40)
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
                low=df_chart['Low'], close=df_chart['Close'], name='Candle Harian'
            )])
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA50'], mode='lines', name='Trend MA50', line=dict(color='#F59E0B', width=1.5)))
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=380)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Data saham tidak ditemukan.")
except Exception as e:
    st.error(f"Gagal memuat analisis harian: {str(e)}")
