import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

st.set_page_config(page_title="Analisis Emiten & S&R", page_icon="📊", layout="wide")

st.title("📊 Analisis Saham, Tren & Support-Resistance (1 Minggu)")
st.write("Masukkan kode emiten saham Indonesia untuk melihat analisis tren mingguan dan titik krusial harga.")

# Input Emiten
ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BBCA, TLKM, BMRI)", "BBCA").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    # Mengambil data agak panjang (1 tahun) agar indikator MA20 tidak error/kosong
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Menghitung matriks tren dan titik S&R...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date)
    
    if not data_saham.empty:
        # 1. DATA HARGA TERAKHIR
        harga_terakhir = float(data_saham['Close'].iloc[-1].iloc[0] if isinstance(data_saham['Close'].iloc[-1], pd.Series) else data_saham['Close'].iloc[-1])
        harga_sebelumnya = float(data_saham['Close'].iloc[-2].iloc[0] if isinstance(data_saham['Close'].iloc[-2], pd.Series) else data_saham['Close'].iloc[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100
        
        # Ringkasan Atas
        col1, col2, col3 = st.columns(3)
        col1.metric("Saham", f"{ticker_input}.JK")
        col2.metric("Harga Terakhir", f"Rp {harga_terakhir:,.0f}")
        col3.metric("Perubahan Harian", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        
        # 2. FILTER DATA 1 MINGGU TERAKHIR (Untuk Tren & S&R)
        data_1_minggu = data_saham.tail(5) # 5 hari bursa = 1 minggu perdagangan
        
        high_1w = float(data_1_minggu['High'].max().iloc[0] if isinstance(data_1_minggu['High'].max(), pd.Series) else data_1_minggu['High'].max())
        low_1w = float(data_1_minggu['Low'].min().iloc[0] if isinstance(data_1_minggu['Low'].min(), pd.Series) else data_1_minggu['Low'].min())
        close_1w = float(data_1_minggu['Close'].iloc[-1].iloc[0] if isinstance(data_1_minggu['Close'].iloc[-1], pd.Series) else data_1_minggu['Close'].iloc[-1])
        close_awal_minggu = float(data_1_minggu['Close'].iloc[0].iloc[0] if isinstance(data_1_minggu['Close'].iloc[0], pd.Series) else data_1_minggu['Close'].iloc[0])
        
        # 3. DETEKSI TREN 1 MINGGU
        persentase_mingguan = ((close_1w - close_awal_minggu) / close_awal_minggu) * 100
        if persentase_mingguan > 1.5:
            tren_1w = "📈 BULLISH (Naik)"
            detektor_tren = f"Saham ini dalam 1 minggu terakhir mengalami kenaikan sebesar {persentase_mingguan:.2f}%. Tekanan beli mendominasi."
        elif persentase_mingguan < -1.5:
            tren_1w = "📉 BEARISH (Turun)"
            detektor_tren = f"Saham ini dalam 1 minggu terakhir mengalami penurunan sebesar {persentase_mingguan:.2f}%. Tekanan jual mendominasi."
        else
