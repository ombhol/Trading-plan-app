import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

st.set_page_config(page_title="Prediksi & Analisis Emiten", page_icon="📊", layout="wide")

st.title("📊 Analisis & Sinyal Arah Saham Harian")
st.write("Aplikasi ini menganalisis tren harian untuk menentukan kecenderungan arah harga.")

# Input Emiten
ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BBCA, TLKM, BMRI)", "BBCA").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    # Ambil data 1 tahun ke belakang agar perhitungan MA valid
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Menghitung matriks dan sinyal pasar...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date)
    
    if not data_saham.empty:
        # Data Harga
        harga_terakhir = data_saham['Close'].iloc[-1].item()
        harga_sebelumnya = data_saham['Close'].iloc[-2].item()
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100
        
        # Ringkasan Atas
        col1, col2, col3 = st.columns(3)
        col1.metric("Saham", f"{ticker_input}.JK")
        col2.metric("Harga Terakhir", f"Rp {harga_terakhir:,.0f}")
        col3.metric("Perubahan Terakhir", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        
        # Perhitungan Indikator
        data_saham['MA20'] = data_saham['Close'].rolling(window=20).mean()
        delta = data_saham['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data_saham['RSI'] = 100 - (100 / (1 + rs))
        
        rsi_terakhir = data_saham['RSI'].iloc[-1].item()
        ma20_terakhir = data_saham['MA20'].iloc[-1].item()
        
        st.markdown("### 🎯 Sinyal & Prediksi Hari Ini")
        
        # LOGIKA PREDIKSI & SINYAL AKSI
        # Kondisi 1: Bullish Kuat
        if harga_terakhir > ma20_terakhir and rsi_terakhir < 70:
            arah_harga = "🟢 KECENDERUNGAN NAIK (BULLISH)"
            rekomendasi = "🛍️ BUY / HOLD (Potensi melanjutkan kenaikan karena tren sehat)"
            warna_box = "success"
        # Kondisi 2: Bearish Kuat
        elif harga_terakhir < ma20_terakhir and rsi_terakhir > 30:
            arah_harga = "🔴 KECENDERUNGAN TURUN (BEARISH)"
            rekomendasi = "⚠️ JANGAN BUY / WAIT AND SEE (Tren jangka pendek melemah)"
            warna_box = "error"
        # Kondisi 3: Overbought (Jenuh Beli)
        elif rsi_terakhir >= 70:
            arah_harga = "🟡 RAWAN KOREKSI (OVERBOUGHT)"
            rekomendasi = "💰 TAKE PROFIT / JANGAN KEJAR ATAS (Harga sudah kemahalan)"
            warna_box = "warning"
        # Kondisi 4: Oversold (Jenuh Jual)
        elif rsi_terakhir <= 30:
            arah_harga = "🔵 POTENSI REBOUND (OVERSOLD)"
            rekomendasi = "🛒 SPEKULASI BUY (Sudah sangat murah, bersiap pantulan naik)"
            warna_box = "info"
        else:
            arah_harga = "⚪ KONSOLIDASI (NETRAL/SIDEWAYS)"
            rekomendasi = "⚖️ HOLD / WAIT AND SEE (Menunggu konfirmasi arah baru)"
            warna_box = "info"
            
        # Tampilkan Hasil Analisis Tegas
        if warna_box == "success":
            st.success(f"**Arah Hari Ini:** {arah_harga}\n\n**Rekomendasi Aksi:** {rekomendasi}")
        elif warna_box == "error":
            st.error(f"**Arah Hari Ini:** {arah_harga}\n\n**Rekomendasi Aksi:** {rekomendasi}")
        elif warna_box == "warning":
            st.warning(f"**Arah Hari Ini:** {arah_harga}\n\n**Rekomendasi Aksi:** {rekomendasi}")
        else:
            st.info(f"**Arah Hari Ini:** {arah_harga}\n\n**Rekomendasi Aksi:** {rekomendasi}")
            
        # Menampilkan Grafik Pendukung
        st.write("---")
        st.write("### 📈 Grafik Pergerakan Harga (vs MA20)")
        chart_data = data_saham[['Close', 'MA20']].tail(90) # Tampilkan 90 hari terakhir saja agar rapi
        st.line_chart(chart_data)
        
        # Detail Angka Indikator
        st.write(f"ℹ️ *Nilai Indikator Saat Ini — RSI: {rsi_terakhir:.2f} | Nilai MA20: Rp {ma20_terakhir:,.0f}*")

    else:
        st.error(f"Gagal mengambil data untuk '{ticker_input}'.")
except Exception as e:
    st.error(f"Terjadi kesalahan teknis sistem. Pastikan file requirements.txt Anda sudah terpasang dengan benar.")
