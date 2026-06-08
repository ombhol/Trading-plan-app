import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Trading Plan Pro - Day Trading 5M", page_icon="📈", layout="wide")

# --- STYLE PREMIUM ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] {
        background-color: #1f2937 !important;
        padding: 15px !important;
        border-radius: 10px !important;
        border: 1px solid #374151 !important;
    }
    div[data-testid="stMetricLabel"] > div { color: #9ca3af !important; font-weight: bold !important; }
    div[data-testid="stMetricValue"] > div { color: #ffffff !important; font-weight: bold !important; }
    .stAlert { border-radius: 10px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 TRADING PLAN PRO - DAY TRADING (5-MIN TIMEFRAME)")
st.write("Screener Multi-Timeframe (Harian + 5 Menit) untuk Setup Probabilitas Tinggi")

ticker_clean = st.text_input("Masukkan Kode Saham Utama (Contoh: PTBA, BRMS, BBCA, BREN)", "BRMS").strip().upper()
ticker_code = f"{ticker_clean}.JK"

st.markdown("---")

# --- FUNGSI AMBIL DATA DIVIDEN (CACHE) ---
@st.cache_data(ttl=3600)
def ambil_dividen_dari_finance(ticker_code):
    try:
        ticker_obj = yf.Ticker(ticker_code)
        hist_div = ticker_obj.dividends
        if not hist_div.empty:
            terakhir_ex_date = hist_div.index[-1]
            nominal = hist_div.iloc[-1]
            estimasi_cum_date = terakhir_ex_date - pd.offsets.BDay(1)
            return {
                "ada": True,
                "nominal": f"Rp {nominal:,.2f}",
                "cum_date": estimasi_cum_date.strftime('%d %B %Y'),
                "ex_date": terakhir_ex_date.strftime('%d %B %Y')
            }
    except Exception:
        pass
    return {"ada": False}

# --- FUNGSI AMBIL BERITA (CACHE) ---
@st.cache_data(ttl=1800)
def ambil_berita_indonesia(ticker):
    daftar_berita = []
    try:
        query = urllib.parse.quote(f"{ticker} saham")
        url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            root = ET.fromstring(response.read())
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            if " - " in title: title = title.rsplit(" - ", 1)[0]
            source = item.find('source').text if item.find('source') is not None else "Media"
            pub_date = item.find('pubDate').text[:16] if item.find('pubDate') is not None else ""
            daftar_berita.append({"title": title, "link": item.find('link').text, "source": source, "date": pub_date})
    except Exception:
        pass
    return daftar_berita

# --- FUNGSI AMBIL DATA HARGA (MULTI-TIMEFRAME) ---
@st.cache_data(ttl=300) # Cache 5 Menit agar sinkron dengan timeframe
def ambil_data_multi_timeframe(ticker_code):
    # Data Harian untuk Tren Makro (1 Tahun terakhir)
    df_daily = yf.download(ticker_code, period="1y", interval="1d")
    # Data Intraday untuk Eksekusi (5 Hari terakhir, per 5 menit)
    df_5m = yf.download(ticker_code, period="5d", interval="5m")
    
    # Fix multi-index issue from latest yfinance update
    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = df_daily.columns.get_level_values(0)
    if isinstance(df_5m.columns, pd.MultiIndex):
        df_5m.columns = df_5m.columns.get_level_values(0)
        
    return df_daily, df_5m

# --- PROSES UTAMA ---
try:
    with st.spinner(f'Menganalisis Multi-Timeframe untuk saham {ticker_clean}...'):
        df_daily, df_5m = ambil_data_multi_timeframe(ticker_code)
        data_dividen = ambil_dividen_dari_finance(ticker_code)
        berita_lokal = ambil_berita_indonesia(ticker_clean)
        
    if df_daily is not None and not df_daily.empty and df_5m is not None and not df_5m.empty:
        
        # 1. ANALISIS TREN HARIAN (MACRO TREND)
        df_daily['MA20'] = df_daily['Close'].rolling(window=20).mean()
        df_daily['MA50'] = df_daily['Close'].rolling(window=50).mean()
        
        daily_close_last = float(df_daily['Close'].iloc[-1])
        daily_ma20_last = float(df_daily['MA20'].iloc[-1])
        daily_ma50_last = float(df_daily['MA50'].iloc[-1])
        
        is_daily_uptrend = (daily_close_last > daily_ma20_last) and (daily_ma20_last > daily_ma50_last)
        
        # Hitung Pivot Poin dari harga hari SEBELUMNYA untuk level S&R hari ini
        prev_high = float(df_daily['High'].iloc[-2])
        prev_low = float(df_daily['Low'].iloc[-2])
        prev_close = float(df_daily['Close'].iloc[-2])
        
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)

        # 2. ANALISIS INTRADAY (5-MINUTE)
        df_5m['MA20'] = df_5m['Close'].rolling(window=20).mean() # Dinamis 5 Menit
        
        # MACD 5-Menit
        exp1 = df_5m['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df_5m['Close'].ewm(span=26, adjust=False).mean()
        df_5m['MACD'] = exp1 - exp2
        df_5m['Signal'] = df_5m['MACD'].ewm(span=9, adjust=False).mean()
        df_5m['MACD_Hist'] = df_5m['MACD'] - df_5m['Signal']
        
        # Volume 5-Menit & Rata-ratanya
        df_5m['Vol_MA20'] = df_5m['Volume'].rolling(window=20).mean()
        
        # Ambil data 5 menit terakhir
        current_price = float(df_5m['Close'].iloc[-1])
        prev_price = float(df_5m['Close'].iloc[-2])
        persentase_ubah_5m = ((current_price - prev_price) / prev_price) * 100
        
        vol_5m_last = float(df_5m['Volume'].iloc[-1])
        vol_5m_avg = float(df_5m['Vol_MA20'].iloc[-1])
        vol_ratio_5m = vol_5m_last / vol_5m_avg if vol_5m_avg > 0 else 1.0
        
        macd_5m = float(df_5m['MACD'].iloc[-1])
        sig_5m = float(df_5m['Signal'].iloc[-1])
        ma20_5m = float(df_5m['MA20'].iloc[-1])

        # --- SISTEM SKORING KETAT (DAY TRADING SETUP) ---
        st.subheader("🔮 ANALISIS DAY TRADING (HIGH PROBABILITY SETUP)")
        
        skor_setup = 0
        alasan_setup = []
        peringatan = []
        
        # Syarat 1: Makro Tren Harian (Filter Paling Penting)
        if is_daily_uptrend:
            skor_setup += 40
            alasan_setup.append("✅ Tren Harian UPTREND (Harga > MA20 & MA20 > MA50)")
        else:
            skor_setup -= 30
            peringatan.append("❌ Tren Harian DOWNTREND / Sideways (Risiko tangkap pisau jatuh tinggi!)")
            
        # Syarat 2: Volume Intraday (5 Menit) - Mencari Smart Money
        if vol_ratio_5m >= 3.0:
            skor_setup += 30
            alasan_setup.append(f"✅ Ledakan Volume 5M Masif ({vol_ratio_5m:.1f}x dari rata-rata)")
        elif vol_ratio_5m >= 1.5:
            skor_setup += 15
            alasan_setup.append(f"✅ Ada Akumulasi Volume 5M ({vol_ratio_5m:.1f}x dari rata-rata)")
        else:
            peringatan.append("⚠️ Volume 5M sepi (Pergerakan rentan False Breakout)")

        # Syarat 3: Momentum MACD 5-Menit
        if macd_5m > sig_5m and macd_5m > 0:
            skor_setup += 20
            alasan_setup.append("✅ Momentum MACD 5M Bullish & Kuat")
        elif macd_5m > sig_5m:
            skor_setup += 10
            alasan_setup.append("✅ MACD 5M Mulai Golden Cross")
            
        # Syarat 4: Posisi Harga vs MA20 5-Menit
        if current_price > ma20_5m:
            skor_setup += 10
            alasan_setup.append("✅ Harga intraday bergerak di atas MA20 (5M)")
            
        # Syarat 5: Katalis Berita
        if berita_lokal:
            skor_setup += 10 # Bonus sentimen

        skor_final = max(0, min(100, skor_setup)) # Normalisasi 0 - 100

        # Tampilan Hasil Evaluasi Setup
        if skor_final >= 80:
            st.success(f"🔥 **HIGH PROBABILITY SETUP! (Skor: {skor_final}/100)** - Sangat Layak Eksekusi")
            st.markdown(f"**Alasan Masuk:**\n" + "\n".join([f"- {item}" for item in alasan_setup]))
        elif 50 <= skor_final < 80:
            st.warning(f"⚡ **MODERATE SETUP (Skor: {skor_final}/100)** - Pantau Pergerakan Harga")
            st.markdown(f"**Alasan Masuk:**\n" + "\n".join([f"- {item}" for item in alasan_setup]))
            if peringatan:
                st.markdown(f"**Perhatikan:**\n" + "\n".join([f"- {item}" for item in peringatan]))
        else:
            st.error(f"🚫 **LOW PROBABILITY / NO TRADE ZONE (Skor: {skor_final}/100)** - Hindari Saham Ini")
            if peringatan:
                st.markdown(f"**Alasan Dihindari:**\n" + "\n".join([f"- {item}" for item in peringatan]))

        st.markdown("---")

        # 3 Kolom Metrik Atas
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN & TREN HARIAN", f"{ticker_clean}", "UPTREND" if is_daily_uptrend else "DOWNTREND/SIDEWAYS", delta_color="normal" if is_daily_uptrend else "inverse")
        col_m2.metric("HARGA SAAT INI", f"Rp {current_price:,.0f}", f"{persentase_ubah_5m:+.2f}% (dlm 5 Menit Terakhir)")
        col_m3.metric("RASIO VOLUME 5-MENIT", f"{vol_ratio_5m:.2f}x", "Ledakan Volume" if vol_ratio_5m > 2 else "Normal", delta_color="normal" if vol_ratio_5m > 2 else "off")

        col_left, col_right = st.columns([1, 1.5])

        with col_left:
            st.subheader("🏹 TRADING PLAN SETUP")
            st.markdown("Berdasarkan *Pivot Point* Harian:")
            st.info(f"🛒 **AREA BUY (Pantau M5):** Sekitar MA20 5M (Rp {int(ma20_5m):,.0f}) atau Support Rp {int(s1):,.0f}")
            st.success(f"🎯 **TARGET (TAKE PROFIT):**\n- TP 1: Rp {int(r1):,.0f}\n- TP 2: Rp {int(r2):,.0f}")
            st.error(f"⚠️ **STRICT STOP LOSS:** Rp {int(s1 * 0.99):,.0f} (Jika candle 5M ditutup di bawah ini, langsung Cut Loss!)")

        with col_right:
            st.subheader("📊 GRAFIK INTRADAY (TIMEFRAME 5 MENIT)")
            # Tarik data intraday terakhir (misal 60 candle terakhir = 5 jam bursa)
            df_plot = df_5m.tail(60)
            
            fig = go.Figure()
            # Candlestick 5 Menit
            fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Harga 5M"))
            # Garis MA20 (5 Menit)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], mode='lines', name='MA20 (Dinamis S/R)', line=dict(color='#3b82f6', width=2)))
            
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=400, xaxis_rangeslider_visible=False, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)

        # --- SEKSI BERITA & DIVIDEN ---
        st.write("---")
        col_bawah1, col_bawah2 = st.columns(2)
        
        with col_bawah1:
            st.subheader("📰 SENTIMEN BERITA (KATALIS)")
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔗 **[{item['title']}]({item['link']})**")
                    st.caption(f"📰 {item['source']} | 🕒 {item['date']}")
            else:
                st.info("Tidak ada katalis berita utama yang terdeteksi hari ini.")
                
        with col_bawah2:
            st.subheader("💰 INFO DIVIDEN")
            if data_dividen["ada"]:
                st.markdown(f"""
                <div style="background-color: #1f2937; padding: 15px; border-radius: 8px; border-left: 5px solid #10B981;">
                    <p style="margin:0; color:white; font-size:15px;"><b>Dividen:</b> <span style="color:#10B981;">{data_dividen['nominal']}</span>/lembar</p>
                    <p style="margin:5px 0 0 0; color:white; font-size:13px;"><b>Cum Date:</b> <span style="color:#FBBF24;">{data_dividen['cum_date']}</span></p>
                    <p style="margin:5px 0 0 0; color:white; font-size:13px;"><b>Ex Date:</b> <span style="color:#EF4444;">{data_dividen['ex_date']}</span></p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Belum ada jadwal dividen terdekat.")

    else:
        st.error("Data saham tidak ditemukan atau market sedang tutup. (Pastikan koneksi internet stabil & kode saham valid, contoh: BBCA)")
except Exception as e:
    st.error(f"Terjadi kesalahan teknis. Detail Error: {str(e)}")
