import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Trading Plan Harian + ARA/ARB Alert", page_icon="📈", layout="wide")

# Gaya Tampilan Premium Bertema Gelap (Dark Mode)
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .stMetric { background-color: #1f2937; padding: 10px; border-radius: 10px; border: 1px solid #374151; }
    h3 { color: #10B981; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 DASHBOARD TRADING PLAN HARIAN & DETEKTOR EKSTREM")
st.write(f"Analisis Pola Candlestick, Peringatan ARB & Keputusan ARA — Update: {date.today().strftime('%d %B %Y')}")

ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BRMS").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Memindai volatilitas bursa harian...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date, interval="1d")
        
    if not data_saham.empty:
        # Pembersihan Multi-Index Kolom dari yfinance
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

        # Hitung Indikator Rata-rata Volume 20 Hari
        data_saham['Vol_Avg'] = data_saham['Volume'].rolling(window=20).mean()
        vol_avg = float(data_saham['Vol_Avg'].iloc[-1])

        # --- LOGIKA BARU: DETEKSI POTENSI ARA / ARB (VOLATILITAS EKSTREM) ---
        status_ekstrem = "NORMAL"
        pesan_ekstrem = ""
        warna_box = "#1f2937" # default abu-abu

        # Cek apakah volume melonjak di atas 2.5 kali lipat dari rata-rata biasanya
        ledakan_volume = volume_arr[-1] > (2.5 * vol_avg)
        
        # Proksi ARA: Harga close sama dengan atau mendekati High, persentase naik tinggi, volume meledak
        harga_terkunci_atas = (high_arr[-1] - harga_terakhir) <= (0.01 * (high_arr[-1] - low_arr[-1]) if (high_arr[-1] - low_arr[-1]) > 0 else 1)
        if ledakan_volume and harga_terkunci_atas and persentase_ubah > 4:
            status_ekstrem = "ARA_POTENTIAL"
            warna_box = "#10B981" # Hijau Sukses
            pesan_ekstrem = "🔥 KEPUTUSAN ARA / MOMENTUM BOOM: Buyer menguasai 100% papan perdagangan. Volume meledak masif! Rekomendasi: HOLD/BUY ON OPEN besok pagi jika belum punya barang, ikuti momentum searah!"

        # Proksi ARB: Harga close sama dengan atau mendekati Low, persentase turun tajam
        harga_terkunci_bawah = (harga_terakhir - low_arr[-1]) <= (0.01 * (high_arr[-1] - low_arr[-1]) if (high_arr[-1] - low_arr[-1]) > 0 else 1)
        if harga_terkunci_bawah and persentase_ubah < -4:
            status_ekstrem = "ARB_WARNING"
            warna_box = "#EF4444" # Merah Bahaya
            pesan_ekstrem = "🚨 PERINGATAN ARB / PANIC SELLING: Seller mengunci harga di batas terendah harian tanpa perlawanan. Rekomendasi: JANGAN FOMO MASUK, JUAL/AVOID terlebih dahulu demi keamanan modal Anda!"


        # --- PEMBACAAN 5 POLA CANDLESTICK HARIAN ---
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
            bull_2 = close_arr[-2] > open_arr[-2]
            bull_3 = close_arr[-3] > open_arr[-3]

            if lshadow_1 >= 2 * body_1 and ushadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("🔨 Hammer")
            if bear_2 and bull_1 and close_arr[-1] >= open_arr[-2] and open_arr[-1] <= close_arr[-2]:
                pola_terdeteksi.append("🔥 Bullish Engulfing")
            if bear_3 and body_2 < 0.3 * body_3 and bull_1 and close_arr[-1] > (open_arr[-3] + close_arr[-3])/2:
                pola_terdeteksi.append("🌅 Morning Star")
            if bull_3 and bull_2 and bull_1 and close_arr[-1] > close_arr[-2] > close_arr[-3]:
                pola_terdeteksi.append("⚔️ Three White Soldiers")
            if ushadow_1 >= 2 * body_1 and lshadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("📐 Inverted Hammer")

        # Hitung Pivot Support & Resistance
        data_1w = data_saham.tail(5)
        h_1w, l_1w, c_1w = float(data_1w['High'].max()), float(data_1w['Low'].min()), float(data_1w['Close'].iloc[-1])
        pivot = (h_1w + l_1w + c_1w) / 3
        r1, r2 = (2 * pivot) - l_1w, pivot + (h_1w - l_1w)
        s1, s2 = (2 * pivot) - h_1w, pivot - (h_1w - l_1w)

        # Nilai Trading Plan Setup
        buy_area_bawah, buy_area_atas = int(s1), int(harga_terakhir)
        stop_loss = int(s2 * 0.99)
        tp1, tp2 = int(r1), int(r1 * 1.03)

        # --- METRIKS UTAMA ATAS DASHBOARD ---
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN SAHAM", f"{ticker_input}.JK", "TF: HARIAN (1D)")
        col_m2.metric("HARGA CLOSE TERAKHIR", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME TRANSAKSI", f"{volume_arr[-1]/1e6:.1f} M", f"Rata-rata 20H: {vol_avg/1e6:.1f} M", delta_color="off")

        st.markdown("---")

        # --- TAMPILAN DATA & GRAFIK CANDLE ---
        col_left, col_right = st.columns([1, 1.2])

        with col_left:
            # 1. BLOK MONITORING ARA / ARB EKSTREM
            st.subheader("🚨 MONITORING VOLATILITAS EKSTREM")
            if status_ekstrem != "NORMAL":
                st.markdown(f"""
                    <div style='background-color:{warna_box}; padding:15px; border-radius:8px; color:white; font-weight:bold;'>
                        {pesan_ekstrem}
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("⚪ **Status Pergerakan:** Pergerakan harga harian masih dalam batas wajar bursa (Tidak terdeteksi akumulasi/distribusi ekstrem calon ARA/ARB).")

            st.write("---")
            
            # 2. PANEL SINYAL CANDLESTICK
            st.subheader("🔮 PEMBACAAN CANDLE & SINYAL BESOK")
            if pola_terdeteksi and status_ekstrem != "ARB_WARNING":
                for pola in pola_terdeteksi:
                    st.success(f"**Pola Reversal Aktif:** {pola}")
                st.markdown("""
                    <div style='background-color:#10B981; padding:12px; border-radius:8px; text-align:center;'>
                        <h4 style='color:white; margin:0;'>🚀 SIGNAL: BUY (UNTUK CANDLE BESOK)</h4>
                    </div>
                """, unsafe_allow_html=True)
            elif status_ekstrem == "ARB_WARNING":
                st.error("❌ **Sinyal Candlestick Dimatikan:** Terdeteksi kepanikan (Panic Selling), abaikan semua pola pola buy sampai harga stabil.")
            else:
                st.write("• Tidak ada 5 pola bullish candlestick utama malam ini. Jalankan taktik antre beli bawah.")

            st.write("---")
            
            # 3. AREA SETUP STRATEGI
            st.subheader("🏹 TRADING PLAN SETUP")
            st.info(f"🛒 **BUY AREA:** Rp {buy_area_bawah:,.0f} - Rp {buy_area_atas:,.0f}")
            st.error(f"⚠️ **STOP LOSS (SL):** Rp {stop_loss:,.0f}")
            st.success(f"🎯 **TARGET UNTUNG:** TP1: Rp {tp1:,.0f} | TP2: Rp {tp2:,.0f}")

        with col_right:
            st.subheader("📊 ANALISIS GRAFIK CANDLESTICK HARIAN")
            df_chart = data_saham.tail(40)
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
                low=df_chart['Low'], close=df_chart['Close'], name='Candle Harian'
            )])
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=410)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Data saham tidak ditemukan.")
except Exception as e:
    st.error(f"Gagal memuat analisis harian: {str(e)}")
