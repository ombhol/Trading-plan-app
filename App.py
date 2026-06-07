import streamlit as st
import pandas as pd
import yfinance as df  # library untuk mengambil data saham global/lokal
from datetime import date, timedelta

# Konfigurasi halaman
st.set_page_config(page_title="Analisis Emiten Saham", page_icon="📊", layout="wide")

st.title("📊 Aplikasi Analisis Emiten Saham")
st.write("Masukkan kode emiten saham Indonesia untuk melihat grafik dan analisis teknikal otomatis.")

# Input Kode Emiten
ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BBCA, TLKM, BMRI, ASII)", "BBCA").upper()

# Saham Indonesia di Yahoo Finance harus diakhiri dengan ".JK"
ticker_code = f"{ticker_input}.JK"

# Pilih Rentang Waktu Data
rentang_waktu = st.selectbox("Pilih Periode Data:", ["3 Bulan", "6 Bulan", "1 Tahun", "3 Tahun"])
hari_ke_belakang = {"3 Bulan": 90, "6 Bulan": 180, "1 Tahun": 365, "3 Tahun": 1095}

st.markdown("---")

try:
    # Mengambil data dari Yahoo Finance
    start_date = date.today() - timedelta(days=hari_ke_belakang[rentang_waktu])
    end_date = date.today()
    
    with st.spinner('Mengambil data saham terbaru...'):
        data_saham = df.download(ticker_code, start=start_date, end=end_date)
    
    if not data_saham.empty:
        # 1. INFORMASI HARGA TERAKHIR
        harga_terakhir = data_saham['Close'].iloc[-1].item()
        harga_sebelumnya = data_saham['Close'].iloc[-2].item()
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Nama Emiten", f"{ticker_input}.JK")
        col2.metric("Harga Penutupan Terakhir", f"Rp {harga_terakhir:,.0f}")
        col3.metric("Perubahan Harian", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        
        # 2. HITUNG INDIKATOR TEKNIKAL OTOMATIS
        # Menghitung Moving Average (MA 20 dan MA 50)
        data_saham['MA20'] = data_saham['Close'].rolling(window=20).mean()
        data_saham['MA50'] = data_saham['Close'].rolling(window=50).mean()
        
        # Menghitung RSI (Relative Strength Index 14)
        delta = data_saham['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data_saham['RSI'] = 100 - (100 / (1 + rs))
        
        rsi_terakhir = data_saham['RSI'].iloc[-1].item()
        ma20_terakhir = data_saham['MA20'].iloc[-1].item()
        
        # 3. GRAFIK PERGERAKAN HARGA
        st.write("### 📈 Grafik Harga & Moving Average (MA20)")
        # Menyiapkan data untuk grafik
        chart_data = data_saham[['Close', 'MA20']].copy()
        # Streamlit line_chart mendeteksi kolom secara otomatis
        st.line_chart(chart_data)
        
        # 4. KESIMPULAN ANALISIS OTOMATIS
        st.write("### 🔍 Hasil Analisis Teknikal Otomatis")
        
        col_an1, col_an2 = st.columns(2)
        
        with col_an1:
            st.write(f"**Indikator RSI (14):** `{rsi_terakhir:.2f}`")
            if rsi_terakhir >= 70:
                st.error("⚠️ **Overbought (Jenuh Beli):** Harga sudah naik terlalu tinggi, rawan aksi ambil untung (profit taking).")
            elif rsi_terakhir <= 30:
                st.success("✅ **Oversold (Jenuh Jual):** Harga sudah turun sangat dalam, ada potensi pantulan naik (rebound).")
            else:
                st.info("🔄 **Netral:** Harga bergerak di area konsolidasi normal.")
                
        with col_an2:
            st.write(f"**Tren vs MA20:** Harga saat ini vs Rata-rata 20 Hari")
            if harga_terakhir > ma20_terakhir:
                st.success("📈 **Bullish (Tren Naik):** Harga bertahan di atas MA20, tren jangka pendek cenderung kuat naik.")
            else:
                st.error("📉 **Bearish (Tren Turun):** Harga berada di bawah MA20, tren jangka pendek cenderung melemah.")

    else:
        st.error(f"Data saham untuk kode '{ticker_input}' tidak ditemukan. Pastikan kode emiten yang Anda masukkan sudah benar.")

except Exception as e:
    st.error(f"Gagal memuat analisis emiten: Kode saham salah atau koneksi server terganggu.")
