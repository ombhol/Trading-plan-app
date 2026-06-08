import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# Konfigurasi Halaman
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
    .top-card {
        background-color: #1f2937; padding: 20px; border-radius: 12px; 
        text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    .top-card:hover { transform: translateY(-5px); }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 TRADING PLAN PRO - DAY TRADING (5-MIN TIMEFRAME)")
st.write("Screener Multi-Timeframe & Rekomendasi Setup Probabilitas Tinggi")

# --- FUNGSI AUTO SCANNER (TOP 3 REKOMENDASI) ---
# Menggunakan cache 5 menit agar tidak lag saat refresh
@st.cache_data(ttl=300)
def scan_top_saham(watchlist):
    hasil_scan = []
    
    for ticker in watchlist:
        ticker_code = f"{ticker}.JK"
        try:
            # Download data tanpa progress bar
            df_daily = yf.download(ticker_code, period="1y", interval="1d", progress=False)
            df_5m = yf.download(ticker_code, period="5d", interval="5m", progress=False)
            
            if df_daily.empty or df_5m.empty:
                continue
                
            # Fix multi-index
            if isinstance(df_daily.columns, pd.MultiIndex):
                df_daily.columns = df_daily.columns.get_level_values(0)
            if isinstance(df_5m.columns, pd.MultiIndex):
                df_5m.columns = df_5m.columns.get_level_values(0)

            # Kalkulasi Daily
            df_daily['MA20'] = df_daily['Close'].rolling(20).mean()
            df_daily['MA50'] = df_daily['Close'].rolling(50).mean()
            is_uptrend = (df_daily['Close'].iloc[-1] > df_daily['MA20'].iloc[-1]) and (df_daily['MA20'].iloc[-1] > df_daily['MA50'].iloc[-1])

            # Kalkulasi 5-Min
            df_5m['Vol_MA20'] = df_5m['Volume'].rolling(20).mean()
            vol_ratio = df_5m['Volume'].iloc[-1] / df_5m['Vol_MA20'].iloc[-1] if df_5m['Vol_MA20'].iloc[-1] > 0 else 1.0
            
            exp1 = df_5m['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df_5m['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            sig = macd.ewm(span=9, adjust=False).mean()
            
            macd_val = macd.iloc[-1]
            sig_val = sig.iloc[-1]
            ma20_5m = df_5m['Close'].rolling(20).mean().iloc[-1]
            current_price = float(df_5m['Close'].iloc[-1])
            
            # Sistem Skor Mini
            skor = 0
            if is_uptrend: skor += 40
            else: skor -= 30
            
            if vol_ratio >= 3.0: skor += 30
            elif vol_ratio >= 1.5: skor += 15
            
            if macd_val > sig_val and macd_val > 0: skor += 20
            elif macd_val > sig_val: skor += 10
            
            if current_price > ma20_5m: skor += 10
            
            skor_final = max(0, min(100, skor))
            
            # Hanya masukkan saham yang Uptrend dan skor lumayan
            if skor_final >= 50:
                hasil_scan.append({
                    "ticker": ticker,
                    "skor": skor_final,
                    "harga": current_price,
                    "vol_ratio": vol_ratio
                })
        except Exception:
            continue

    # Urutkan berdasarkan skor tertinggi
    hasil_scan = sorted(hasil_scan, key=lambda x: x['skor'], reverse=True)
    return hasil_scan[:3]

# --- 1. SEKSI TOP 3 REKOMENDASI ---
st.subheader("🏆 TOP 3 REKOMENDASI DAY TRADING HARI INI")
st.caption("Dihitung otomatis dari pantauan saham Liquid & Volatil (Di-refresh setiap 5 menit)")

# DAFTAR PANTAUAN (Anda bisa mengubah/menambah daftar ini sesuka hati)
DAFTAR_PANTAUAN = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", # Bluechips
    "BRMS", "BREN", "AMMN", "PTBA", "ADRO", "PGAS", # Komoditas & Energi
    "GOTO", "PANI", "KPIG", "ANTM", "CUAN", "BRPT"  # Volatilitas Tinggi
]

with st.spinner("Memindai ratusan data indikator di latar belakang..."):
    top_3_saham = scan_top_saham(DAFTAR_PANTAUAN)

if top_3_saham:
    cols_top = st.columns(3)
    for i, data in enumerate(top_3_saham):
        with cols_top[i]:
            warna_skor = "#10B981" if data['skor'] >= 80 else "#FBBF24"
            st.markdown(f"""
            <div class="top-card" style="border-top: 5px solid {warna_skor};">
                <h2 style="margin: 0; color: white;">{data['ticker']}</h2>
                <h1 style="margin: 5px 0; color: {warna_skor};">{data['skor']}</h1>
                <p style="margin: 0; color: #9CA3AF; font-size: 14px;">Skor Setup</p>
                <hr style="border-color: #374151; margin: 10px 0;">
                <p style="margin: 0; color: white; font-weight: bold;">Rp {data['harga']:,.0f}</p>
                <p style="margin: 0; color: #9CA3AF; font-size: 13px;">Vol Ratio: {data['vol_ratio']:.1f}x</p>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Market sedang tidak bersahabat. Belum ada setup probabilitas tinggi (Skor > 50) dari daftar pantauan saat ini.")

st.markdown("---")

# --- 2. SEKSI DEEP DIVE (ANALISIS MENDALAM 1 SAHAM) ---
st.subheader("🔎 DEEP DIVE ANALISIS (CEK SAHAM SPESIFIK)")
ticker_clean = st.text_input("Ketik kode saham untuk melihat Trading Plan lengkap (Contoh: ketik salah satu dari Top 3 di atas):", "BRMS").strip().upper()
ticker_code = f"{ticker_clean}.JK"

# --- FUNGSI AMBIL DATA DIVIDEN (Sama seperti sebelumnya) ---
@st.cache_data(ttl=3600)
def ambil_dividen_dari_finance(ticker_code):
    try:
        ticker_obj = yf.Ticker(ticker_code)
        hist_div = ticker_obj.dividends
        if not hist_div.empty:
            today = pd.Timestamp(date.today())
            info_dividen = {"ada": True, "status_upcoming": False, "terakhir": None, "upcoming": None}
            
            def hitung_tanggal_bei(ex_date, nominal):
                ex_date_clean = ex_date.tz_localize(None) if ex_date.tzinfo else ex_date
                cum_date = ex_date_clean - pd.offsets.BDay(1)
                register_date = ex_date_clean + pd.offsets.BDay(1)
                return {
                    "nominal": f"Rp {nominal:,.2f}",
                    "cum_date": cum_date.strftime('%d %b %Y'),
                    "ex_date": ex_date_clean.strftime('%d %b %Y'),
                    "register_date": register_date.strftime('%d %b %Y'),
                    "tanggal_asli": ex_date_clean
                }

            data_paling_akhir = hitung_tanggal_bei(hist_div.index[-1], hist_div.iloc[-1])
            if data_paling_akhir["tanggal_asli"] >= today:
                info_dividen["status_upcoming"] = True
                info_dividen["upcoming"] = data_paling_akhir
                if len(hist_div) > 1:
                    info_dividen["terakhir"] = hitung_tanggal_bei(hist_div.index[-2], hist_div.iloc[-2])
            else:
                info_dividen["terakhir"] = data_paling_akhir
            return info_dividen
    except Exception:
        pass
    return {"ada": False}

# --- FUNGSI AMBIL BERITA (Sama seperti sebelumnya) ---
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

@st.cache_data(ttl=300)
def ambil_data_multi_timeframe(ticker_code):
    df_daily = yf.download(ticker_code, period="1y", interval="1d", progress=False)
    df_5m = yf.download(ticker_code, period="5d", interval="5m", progress=False)
    if isinstance(df_daily.columns, pd.MultiIndex): df_daily.columns = df_daily.columns.get_level_values(0)
    if isinstance(df_5m.columns, pd.MultiIndex): df_5m.columns = df_5m.columns.get_level_values(0)
    return df_daily, df_5m

# --- PROSES UTAMA (DEEP DIVE) ---
try:
    with st.spinner(f'Mengambil data detail untuk {ticker_clean}...'):
        df_daily, df_5m = ambil_data_multi_timeframe(ticker_code)
        data_dividen = ambil_dividen_dari_finance(ticker_code)
        berita_lokal = ambil_berita_indonesia(ticker_clean)
        
    if df_daily is not None and not df_daily.empty and df_5m is not None and not df_5m.empty:
        
        # Kalkulasi Daily
        df_daily['MA20'] = df_daily['Close'].rolling(window=20).mean()
        df_daily['MA50'] = df_daily['Close'].rolling(window=50).mean()
        is_daily_uptrend = (float(df_daily['Close'].iloc[-1]) > float(df_daily['MA20'].iloc[-1])) and (float(df_daily['MA20'].iloc[-1]) > float(df_daily['MA50'].iloc[-1]))
        
        prev_high, prev_low, prev_close = float(df_daily['High'].iloc[-2]), float(df_daily['Low'].iloc[-2]), float(df_daily['Close'].iloc[-2])
        pivot = (prev_high + prev_low + prev_close) / 3
        r1, r2 = (2 * pivot) - prev_low, pivot + (prev_high - prev_low)
        s1, s2 = (2 * pivot) - prev_high, pivot - (prev_high - prev_low)

        # Kalkulasi 5-Min
        df_5m['MA20'] = df_5m['Close'].rolling(window=20).mean()
        df_5m['Vol_MA20'] = df_5m['Volume'].rolling(window=20).mean()
        exp1, exp2 = df_5m['Close'].ewm(span=12, adjust=False).mean(), df_5m['Close'].ewm(span=26, adjust=False).mean()
        df_5m['MACD'] = exp1 - exp2
        df_5m['Signal'] = df_5m['MACD'].ewm(span=9, adjust=False).mean()
        
        current_price = float(df_5m['Close'].iloc[-1])
        persentase_ubah_5m = ((current_price - float(df_5m['Close'].iloc[-2])) / float(df_5m['Close'].iloc[-2])) * 100
        vol_ratio_5m = float(df_5m['Volume'].iloc[-1]) / float(df_5m['Vol_MA20'].iloc[-1]) if float(df_5m['Vol_MA20'].iloc[-1]) > 0 else 1.0
        macd_5m, sig_5m, ma20_5m = float(df_5m['MACD'].iloc[-1]), float(df_5m['Signal'].iloc[-1]), float(df_5m['MA20'].iloc[-1])

        # Skoring Setup Detail
        skor_setup = 0
        alasan_setup = []
        peringatan = []
        
        if is_daily_uptrend: skor_setup += 40; alasan_setup.append("✅ Tren Harian UPTREND (Harga > MA20 & MA20 > MA50)")
        else: skor_setup -= 30; peringatan.append("❌ Tren Harian DOWNTREND / Sideways")
            
        if vol_ratio_5m >= 3.0: skor_setup += 30; alasan_setup.append(f"✅ Ledakan Volume 5M Masif ({vol_ratio_5m:.1f}x)")
        elif vol_ratio_5m >= 1.5: skor_setup += 15; alasan_setup.append(f"✅ Akumulasi Volume 5M ({vol_ratio_5m:.1f}x)")
        else: peringatan.append("⚠️ Volume 5M sepi (Rentan False Breakout)")

        if macd_5m > sig_5m and macd_5m > 0: skor_setup += 20; alasan_setup.append("✅ Momentum MACD 5M Bullish & Kuat")
        elif macd_5m > sig_5m: skor_setup += 10; alasan_setup.append("✅ MACD 5M Mulai Golden Cross")
            
        if current_price > ma20_5m: skor_setup += 10; alasan_setup.append("✅ Harga intraday di atas MA20 (5M)")
        if berita_lokal: skor_setup += 10
            
        skor_final = max(0, min(100, skor_setup))

        # 3 Kolom Metrik
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN & TREN HARIAN", f"{ticker_clean}", "UPTREND" if is_daily_uptrend else "DOWNTREND/SIDEWAYS", delta_color="normal" if is_daily_uptrend else "inverse")
        col_m2.metric("HARGA SAAT INI", f"Rp {current_price:,.0f}", f"{persentase_ubah_5m:+.2f}% (5 Menit Terakhir)")
        col_m3.metric("SKOR SETUP SAHAM INI", f"{skor_final} / 100", "Bagus Untuk Day Trade" if skor_final >= 80 else "Hindari / Wait & See", delta_color="normal" if skor_final >= 80 else "off")

        col_left, col_right = st.columns([1, 1.5])

        with col_left:
            st.subheader("🏹 TRADING PLAN SETUP")
            st.info(f"🛒 **AREA BUY (Pantau M5):** Area Rp {int(ma20_5m):,.0f} atau Support Rp {int(s1):,.0f}")
            st.success(f"🎯 **TARGET (TAKE PROFIT):**\n- TP 1: Rp {int(r1):,.0f}\n- TP 2: Rp {int(r2):,.0f}")
            st.error(f"⚠️ **STRICT STOP LOSS:** Rp {int(s1 * 0.99):,.0f} (Cut Loss jika jebol!)")
            
            # Tampilan Kesimpulan Detail
            st.markdown("<br>", unsafe_allow_html=True)
            if skor_final >= 80:
                st.success("**KESIMPULAN: HIGH PROBABILITY!**")
                st.markdown("\n".join([f"- {i}" for i in alasan_setup]))
            else:
                st.error("**KESIMPULAN: LOW PROBABILITY / BERISIKO**")
                st.markdown("\n".join([f"- {i}" for i in peringatan]))

        with col_right:
            st.subheader("📊 GRAFIK INTRADAY (5 MENIT)")
            df_plot = df_5m.tail(60)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Harga 5M"))
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], mode='lines', name='MA20 (Dinamis S/R)', line=dict(color='#3b82f6', width=2)))
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=380, xaxis_rangeslider_visible=False, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)

        # --- SEKSI BERITA & DIVIDEN ---
        st.write("---")
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            st.subheader("📰 SENTIMEN BERITA")
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔗 **[{item['title']}]({item['link']})**")
                    st.caption(f"📰 {item['source']} | 🕒 {item['date']}")
            else: st.info("Tidak ada katalis berita utama.")
                
        with col_b2:
            st.subheader("💰 INFO DIVIDEN")
            if data_dividen["ada"]:
                if data_dividen.get("status_upcoming") and data_dividen.get("upcoming"):
                    upc = data_dividen["upcoming"]
                    st.markdown(f"""
                    <div style="background-color: #1f2937; padding: 15px; border-radius: 8px; border-left: 5px solid #10B981; margin-bottom: 10px;">
                        <h5 style="margin:0; color:#10B981;">📢 DIVIDEN AKAN DATANG!</h5>
                        <p style="margin:5px 0 10px 0; color:white; font-size:15px;"><b>Nominal:</b> <span style="color:#10B981; font-weight:bold;">{upc['nominal']}</span> / lembar</p>
                        <table style="width:100%; color:white; font-size:13px; border-collapse: collapse;">
                            <tr><td><b>🛒 Cum Date:</b></td><td style="color:#FBBF24;">{upc['cum_date']}</td></tr>
                            <tr><td><b>🛑 Ex Date:</b></td><td style="color:#EF4444;">{upc['ex_date']}</td></tr>
                            <tr><td><b>📝 Register Date:</b></td><td style="color:#60A5FA;">{upc['register_date']}</td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                if data_dividen.get("terakhir"):
                    ter = data_dividen["terakhir"]
                    st.markdown(f"""
                    <div style="background-color: #111827; padding: 12px; border-radius: 8px; border-left: 5px solid #6B7280;">
                        <h6 style="margin:0; color:#9CA3AF;">🕰️ RIWAYAT TERAKHIR DIBERIKAN</h6>
                        <table style="width:100%; margin-top:8px; color:#D1D5DB; font-size:13px;">
                            <tr><td width="40%"><b>Nominal:</b></td><td>{ter['nominal']} / lembar</td></tr>
                            <tr><td><b>Cum Date:</b></td><td>{ter['cum_date']}</td></tr>
                            <tr><td><b>Ex Date:</b></td><td>{ter['ex_date']}</td></tr>
                            <tr><td><b>Register Date:</b></td><td>{ter['register_date']}</td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info("Tidak ada riwayat pembagian dividen.")

    else: st.error("Data saham tidak ditemukan.")
except Exception as e:
    st.error(f"Terjadi kesalahan teknis. Detail Error: {str(e)}")
