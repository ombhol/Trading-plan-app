import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Trading Plan Pro Dashboard", page_icon="📈", layout="wide")

# Gaya CSS untuk membuat tampilan bertema gelap/elegan mirip infografis
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .stMetric { background-color: #1f2937; padding: 10px; border-radius: 10px; border: 1px solid #374151; }
    h3 { color: #10B981; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 DASHBOARD TRADING PLAN & TEKNIKAL PRO")
st.write(f"Analisis komprehensif disesuaikan otomatis — Pembaruan Terakhir: {date.today().strftime('%d %B %Y')}")

ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BRMS").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

try:
    # Ambil data harian 1 tahun untuk kestabilan kalkulasi indikator
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Menyinkronkan data bursa dan indikator teknikal...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date)
        
    if not data_saham.empty:
        # Ekstrak data skalar dengan aman dari Pandas DataFrame
        def get_scaler(series, idx=-1):
            val = series.iloc[idx]
            return float(val.values[0] if hasattr(val, 'values') else val)

        harga_terakhir = get_scaler(data_saham['Close'])
        harga_sebelumnya = get_scaler(data_saham['Close'], -2)
        high_terakhir = get_scaler(data_saham['High'])
        low_terakhir = get_scaler(data_saham['Low'])
        volume_terakhir = get_scaler(data_saham['Volume'])
        
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100

        # --- HITUNG INDIKATOR TEKNIKAL SECARA MANUAL (LEBIH AMAN & STABIL) ---
        # 1. MA50
        data_saham['MA50'] = data_saham['Close'].rolling(window=50).mean()
        ma50_sekarang = get_scaler(data_saham['MA50'])
        
        # 2. MACD (12, 26, 9)
        exp12 = data_saham['Close'].ewm(span=12, adjust=False).mean()
        exp26 = data_saham['Close'].ewm(span=26, adjust=False).mean()
        data_saham['MACD'] = exp12 - exp26
        data_saham['Signal'] = data_saham['MACD'].ewm(span=9, adjust=False).mean()
        macd_val = get_scaler(data_saham['MACD'])
        signal_val = get_scaler(data_saham['Signal'])
        
        # 3. Stochastic Oscillator (14, 3)
        low_14 = data_saham['Low'].rolling(window=14).min()
        high_14 = data_saham['High'].rolling(window=14).max()
        data_saham['Stoch_K'] = 100 * ((data_saham['Close'] - low_14) / (high_14 - low_14))
        data_saham['Stoch_D'] = data_saham['Stoch_K'].rolling(window=3).mean()
        stoch_k = get_scaler(data_saham['Stoch_K'])

        # 4. Deteksi Big Money / Volume Spike (Rata-rata volume 20 hari)
        data_saham['Vol_Avg'] = data_saham['Volume'].rolling(window=20).mean()
        vol_avg = get_scaler(data_saham['Vol_Avg'])
        big_money_status = "🟢 DI ATAS RATA-RATA" if volume_terakhir > vol_avg else "⚪ NORMAL"

        # --- HITUNG AREA LEVEL PENTING (S&R 1 Minggu) ---
        data_1w = data_saham.tail(5)
        h_1w = float(data_1w['High'].max().values[0] if hasattr(data_1w['High'].max(), 'values') else data_1w['High'].max())
        l_1w = float(data_1w['Low'].min().values[0] if hasattr(data_1w['Low'].min(), 'values') else data_1w['Low'].min())
        c_1w = float(data_1w['Close'].iloc[-1].values[0] if hasattr(data_1w['Close'].iloc[-1], 'values') else data_1w['Close'].iloc[-1])
        
        pivot = (h_1w + l_1w + c_1w) / 3
        r1, r2 = (2 * pivot) - l_1w, pivot + (h_1w - l_1w)
        s1, s2 = (2 * pivot) - h_1w, pivot - (h_1w - l_1w)

        buy_area_bawah, buy_area_atas = int(s1), int(harga_terakhir)
        stop_loss = int(s2 * 0.99)
        tp1, tp2, tp3 = int(r1), int(r1 * 1.02), int(r2)

        # --- SISTEM POSISI SKENARIO & PROBABILITAS ---
        skor_bullish = 0
        if harga_terakhir > ma50_sekarang: skor_bullish += 1
        if macd_val > signal_val: skor_bullish += 1
        if stoch_k > 50: skor_bullish += 1
        if volume_terakhir > vol_avg: skor_bullish += 1

        if skor_bullish >= 3:
            p_bullish, p_sideways, p_bearish = "60%", "25%", "15%"
            tren_label = "BULLISH CONSOLIDATION"
        elif skor_bullish == 2:
            p_bullish, p_sideways, p_bearish = "35%", "45%", "20%"
            tren_label = "SIDEWAYS / NETRAL"
        else:
            p_bullish, p_sideways, p_bearish = "15%", "25%", "60%"
            tren_label = "BEARISH TREND"

        # --- TAMPILAN INTERFACE UTAMA ---
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("EMITEN SAHAM", f"{ticker_input}.JK", tren_label)
        col_m2.metric("HARGA SAAT INI", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME AKTIVITAS", f"{volume_terakhir/1e6:.1f} M", f"Aksi Pasar: {big_money_status}", delta_color="off")
        col_m4.metric("STOCHASTIC K-D", f"{stoch_k:.1f}", "Momentum Pasar")

        st.markdown("---")

        # Layout Kolom Kiri (Data) & Kanan (Grafik Candlestick)
        col_data, col_chart = st.columns([1, 1.3])

        with col_data:
            tab1, tab2 = st.tabs(["🏹 TRADING PLAN", "📋 CHECKLIST TEKNIKAL"])
            
            with tab1:
                st.write("### 🚨 LEVEL PENTING")
                st.error(f"**RESISTANCE:** R2: Rp {r2:,.0f} | R1: Rp {r1:,.0f}")
                st.success(f"**SUPPORT:** S1: Rp {s1:,.0f} | S2: Rp {s2:,.0f}")
                
                st.write("### 🟩 AREA STRATEGI")
                st.info(f"**BUY AREA:** Rp {buy_area_bawah:,.0f} - Rp {buy_area_atas:,.0f}")
                st.markdown(f"<h4 style='color:#EF4444; margin:0;'>STOP LOSS: Rp {stop_loss:,.0f}</h4>", unsafe_allow_html=True)
                
                st.write("### 🎯 TARGET AMBIL UNTUNG")
                st.success(f"**TP1:** Rp {tp1:,.0f} | **TP2:** Rp {tp2:,.0f} | **TP3:** Rp {tp3:,.0f}")

            with tab2:
                st.write("### 🔍 KONDISI PASAR (15M / DAILY CONFLUENCE)")
                st.write(f"✅ **Harga > MA50:** {'Sesuai' if harga_terakhir > ma50_sekarang else 'Di bawah rata-rata'}")
                st.write(f"✅ **MACD Positif:** {'Bullish Cross' if macd_val > signal_val else 'Bearish Cross'}")
                st.write(f"✅ **Stochastic Momentum:** {stoch_k:.1f} ({'Oversold/Murah' if stoch_k < 30 else 'Normal/Strong'})")
                
                st.write("### 🔮 PROBABILITAS SKENARIO")
                st.success(f"🟩 **BULLISH ({p_bullish} Peluang):** Kuat di atas Rp {s1:,.0f} menuju target TP.")
                st.warning(f"🟨 **SIDEWAYS ({p_sideways} Peluang):** Konsolidasi sehat di batas aman.")
                st.error(f"🟥 **BEARISH ({p_bearish} Peluang):** Jual jika jebol titik Stop Loss.")

        with col_chart:
            st.write("### 📊 GRAFIK KANDIL (CANDLESTICK) & MA50")
            # Membuat grafik lilin profesional menggunakan Plotly
            df_g = data_saham.tail(45) # Ambil 45 hari terakhir biar rapi di layar HP
            fig = go.Figure(data=[go.Candlestick(
                x=df_g.index,
                open=df_g['Open'], high=df_g['High'],
                low=df_g['Low'], close=df_g['Close'],
                name='Candlestick'
            )])
            fig.add_trace(go.Scatter(x=df_g.index, y=df_g['MA50'], mode='lines', name='MA50', line=dict(color='#F59E0B', width=1.5)))
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=400, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Kode Emiten Tidak Ditemukan.")
except Exception as e:
    st.error("Terjadi error sistem, pastikan file requirements.txt Anda sudah diperbarui.")
