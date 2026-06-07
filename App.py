import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

st.set_page_config(page_title="Analisis Emiten & S&R", page_icon="📊", layout="wide")

st.title("📊 Analisis Saham, Tren & Support-Resistance (1 Minggu)cek by danang")
st.write("Masukkan kode emiten saham Indonesia untuk melihat analisis tren mingguan dan titik krusial harga.")

# Input Emiten
ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BBCA, TLKM, BMRI)", "BBCA").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    # Mengambil data 1 tahun ke belakang agar indikator valid
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Menghitung matriks tren dan titik S&R...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date)
    
    if not data_saham.empty:
        # 1. DATA HARGA TERAKHIR (Menggunakan pencarian nilai skalar yang aman)
        harga_terakhir = float(data_saham['Close'].iloc[-1].values[0] if hasattr(data_saham['Close'].iloc[-1], 'values') else data_saham['Close'].iloc[-1])
        harga_sebelumnya = float(data_saham['Close'].iloc[-2].values[0] if hasattr(data_saham['Close'].iloc[-2], 'values') else data_saham['Close'].iloc[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100
        
        # Ringkasan Atas
        col1, col2, col3 = st.columns(3)
        col1.metric("Saham", f"{ticker_input}.JK")
        col2.metric("Harga Terakhir", f"Rp {harga_terakhir:,.0f}")
        col3.metric("Perubahan Harian", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        
        # 2. FILTER DATA 1 MINGGU TERAKHIR (5 hari bursa)
        data_1_minggu = data_saham.tail(5)
        
        high_1w = float(data_1_minggu['High'].max().values[0] if hasattr(data_1_minggu['High'].max(), 'values') else data_1_minggu['High'].max())
        low_1w = float(data_1_minggu['Low'].min().values[0] if hasattr(data_1_minggu['Low'].min(), 'values') else data_1_minggu['Low'].min())
        close_1w = float(data_1_minggu['Close'].iloc[-1].values[0] if hasattr(data_1_minggu['Close'].iloc[-1], 'values') else data_1_minggu['Close'].iloc[-1])
        close_awal_minggu = float(data_1_minggu['Close'].iloc[0].values[0] if hasattr(data_1_minggu['Close'].iloc[0], 'values') else data_1_minggu['Close'].iloc[0])
        
        # 3. DETEKSI TREN 1 MINGGU
        persentase_mingguan = ((close_1w - close_awal_minggu) / close_awal_minggu) * 100
        
        if persentase_mingguan > 1.5:
            tren_1w = "📈 BULLISH (Naik)"
            detektor_tren = f"Saham ini dalam 1 minggu terakhir mengalami kenaikan sebesar {persentase_mingguan:.2f}%. Tekanan beli mendominasi."
        elif persentase_mingguan < -1.5:
            tren_1w = "📉 BEARISH (Turun)"
            detektor_tren = f"Saham ini dalam 1 minggu terakhir mengalami penurunan sebesar {persentase_mingguan:.2f}%. Tekanan jual mendominasi."
        else:
            tren_1w = "🔄 SIDEWAYS (Datar)"
            detektor_tren = f"Saham cenderung bergerak stabil dengan perubahan tipis ({persentase_mingguan:.2f}%) dalam minggu ini."
            
        # 4. PERHITUNGAN SUPPORT & RESISTANCE (Pivot Points)
        pivot = (high_1w + low_1w + close_1w) / 3
        resistance_1 = (2 * pivot) - low_1w
        support_1 = (2 * pivot) - high_1w
        
        # TAMPILKAN MATRIKS ANALISIS
        st.write("### 📌 Hasil Analisis Tren & Batas Harga (1 Minggu)")
        col_tren, col_sr = st.columns(2)
        
        with col_tren:
            st.info(f"**Tren 1 Minggu Terakhir:**\n### {tren_1w}\n\n*{detektor_tren}*")
            st.write("---")
            st.write("**💡 Proyeksi Arah Hari Ini:**")
            
            if harga_terakhir >= resistance_1:
                st.warning("⚠️ Harga sudah menyentuh/menembus Resistance. Rawan jenuh beli, waspada pembalikan arah turun.")
            elif harga_terakhir <= support_1:
                st.success("🛒 Harga sudah menyentuh/menembus Support. Ada potensi daya beli masuk untuk memantulkan harga naik.")
            else:
                st.write("🔄 Harga bergerak di area normal di antara Support & Resistance.")

        with col_sr:
            st.write("**📍 Titik Support & Resistance Mingguan:**")
            sr_table = pd.DataFrame({
                'Level Teknis': ['Resistance 1 (Batas Atas)', 'Titik Tengah (Pivot)', 'Support 1 (Batas Bawah)'],
                'Nilai Harga': [f"Rp {resistance_1:,.0f}", f"Rp {pivot:,.0f}", f"Rp {support_1:,.0f}"],
                'Keterangan': ['Target Ambil Untung / Jual', 'Harga Keseimbangan', 'Target Beli / Pantulan']
            })
            st.table(sr_table)
            
        # 5. GRAFIK KINERJA SAHAM
        st.write("---")
        st.write("### 📈 Grafik Pergerakan Harga (90 Hari Terakhir)")
        st.line_chart(data_saham['Close'].tail(90))

    else:
        st.error(f"Gagal mengambil data untuk '{ticker_input}'.")
        
except Exception as e:
    st.error(f"Terjadi kesalahan pembacaan data emiten. Silakan coba beberapa saat lagi.")
