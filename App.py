import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Trading Plan Harian + ARA/ARB + News", page_icon="📈", layout="wide")

# --- PERBAIKAN TOTAL SCRIPT CSS (Warna Teks Kotak Metrik Dipaksa Putih Bersih) ---
st.markdown("""
    <style>
    /* Background utama halaman */
    .main { background-color: #0e1117; }
    
    /* Box Metrik */
    div[data-testid="stMetric"] {
        background-color: #1f2937 !important;
        padding: 15px !important;
        border-radius: 10px !important;
        border: 1px solid #374151 !important;
    }
    
    /* Warna teks Judul Metrik (Atas) */
    div[data-testid="stMetricLabel"] > div {
        color: #9ca3af !important;
        font-weight: bold !important;
    }
    
    /* Warna teks Angka Utama/Harga Metrik (Tengah) */
    div[data-testid="stMetricValue"] > div {
        color: #ffffff !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 DASHBOARD TRADING PLAN HARIAN & DETEKTOR EKSTREM")
st.write(f"Analisis Pola Candlestick, Peringatan ARB & Berita Fundamental — Update: {date.today().strftime('%d %B %Y')}")

ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BRMS").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Memindai data pasar dan berita terbaru...'):
        # Ambil data pergerakan harga
        data_saham = yf.download(ticker_code, start=start_date, end=end_date, interval="1d")
        
        # Ambil data berita fundamental emiten secara real-time
        try:
            ticker_obj = yf.Ticker(ticker_code)
            berita_saham = ticker_obj.news
        except:
            berita_saham = []
        
    if not data_saham.empty:
        if isinstance(data_saham.columns, pd.MultiIndex):
            data_saham.columns = data_saham.columns.get_level_values(0)
            
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if isinstance(data_saham[col], pd.DataFrame):
                data_saham[col] = data_saham[col].iloc[:, 0]

        open_arr = data_saham['Open'].values
        high_arr = data_saham['High'].values
        low_arr = data_saham['Low'].values
        close_arr = data_saham['Close'].values
        volume_arr = data_saham['Volume'].values

        harga_terakhir = float(close_arr[-1])
        harga_sebelumnya = float(close_arr[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100

        data_saham['Vol_Avg'] = data_saham['Volume'].rolling(window=20).mean()
        vol_avg = float(data_saham['Vol_Avg'].iloc[-1])

        # --- LOGIKA DETEKSI POTENSI ARA / ARB ---
        status_ekstrem = "NORMAL"
        pesan_ekstrem = ""
        warna_box = "#1f2937"

        ledakan_volume = volume_arr[-1] > (2.5 * vol_avg)
        harga_terkunci_atas = (high_arr[-1] - harga_terakhir) <= (0.01 * (high_arr[-1] - low_arr[-1]) if (high_arr[-1] - low_arr[-1]) > 0 else 1)
        
        if ledakan_volume and harga_terkunci_atas and persentase_ubah > 4:
            status_ekstrem = "ARA_POTENTIAL"
            warna_box = "#10B981"
            pesan_ekstrem = "🔥 KEPUTUSAN ARA / MOMENTUM BOOM: Buyer menguasai 100% papan perdagangan. Volume meledak masif! Rekomendasi: HOLD/BUY ON OPEN besok pagi jika belum punya barang, ikuti momentum searah!"

        harga_terkunci_bawah = (harga_terakhir - low_arr[-1]) <= (0.01 * (high_arr[-1] - low_arr[-1]) if (high_arr[-1] - low_arr[-1]) > 0 else 1)
        if harga_terkunci_bawah and persentase_ubah < -4:
            status_ekstrem = "ARB_WARNING"
            warna_box = "#EF4444"
            pesan_ekstrem = "🚨 PERINGATAN ARB / PANIC SELLING: Seller mengunci harga di batas terendah harian tanpa perlawanan. Rekomendasi: JANGAN FOMO MASUK, JUAL/AVOID terlebih dahulu demi keamanan modal Anda!"

        # --- PEMBACAAN 5 POLA CANDLESTICK ---
        pola_terdeteksi = []
        if len(close_arr) >= 4:
            body_1 = abs(close_arr[-1] - open_arr[-1])
            ushadow_1 = high_arr[-1] - max(open_arr[-1], close_arr[-1])
            lshadow_1 = min(open_arr[-1], close_arr[-1]) - low_arr[-1]
            body_2 = abs(close_arr[-2] - open_arr[-2])
            bear_2 = close_arr[-2] < open_arr[-2]
            bull_1 = close_arr[-1] > open_arr[-1]
            body_3 = abs(close_arr[-3] - open_arr[-3])
            bear_3 = close_arr[-3] < open_arr[-3]
            bull_2 = close_2 = close_arr[-2] > open_arr[-2]
            bull_3 = close_arr[-3] > open_arr[-3]

            if lshadow_1 >= 2 * body_1 and ushadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("🔨 Hammer")
            if bear_2 and bull_1 and close_arr[-1] >= open_arr[-2] and open_arr[-1] <= close_arr[-2]:
                pola_terdet
