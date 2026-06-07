import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Trading Plan Pro - Super Stable", page_icon="📈", layout="wide")

# --- STYLE PREMIUM ANTI-BLUR ---
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
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 DASHBOARD TRADING PLAN HARIAN & INTELLIGENCE NEWS")
st.write(f"Analisis Teknikal Terintegrasi Agregator Berita Indonesia — Update: {date.today().strftime('%d %B %Y')}")

# Input Ticker Otomatis Dibersihkan dari Spasi
ticker_clean = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BBCA").strip().upper()
ticker_code = f"{ticker_clean}.JK"

st.markdown("---")

# --- FUNGSI AMBIL BERITA & SENTIMEN DIVIDEN (AMAN & KEBAL EROR) ---
def ambil_sentimen_dan_berita(ticker):
    daftar_berita = []
    info_dividen = {"ada": False}
    try:
        query = urllib.parse.quote(f"{ticker} saham")
        url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            link = item.find('link').text
            pub_date = item.find('pubDate').text
            source = item.find('source').text if item.find('source') is not None else "Media Lokal"
            
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
                
            daftar_berita.append({"title": title, "link": link, "source": source, "date": pub_date[:16]})
            
            if any(x in title.lower() for x in ["dividen", "cum", "ex", "rups", "bagi"]):
                if not info_dividen["ada"]:
                    info_dividen = {"ada": True, "judul": title, "link": link, "sumber": source}
    except:
        pass  # Jika internet/Google News bermasalah, aplikasi tidak akan crash
    return daftar_berita, info_dividen

# --- PROSES DOWNLOAD & VALIDASI DATA (ANTI-MULTIINDEX CRASH) ---
try:
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner(f'Mengunduh data saham {ticker_clean}...'):
        # Download data dari Yahoo Finance
        df_raw = yf.download(ticker_code, start=start_date, end=end_date, interval="1d")
        berita_lokal, dividen_lokal = ambil_sentimen_dan_berita(ticker_clean)
        
    if df_raw is not None and not df_raw.empty:
        # PEMBERSIHAN KRUSIAL: Memaksa tabel agar tidak berbentuk MultiIndex
        data_saham = df_raw.copy()
        if isinstance(data_saham.columns, pd.MultiIndex):
            data_saham.columns = data_saham.columns.get_level_values(0)
            
        # Memastikan data dikonversi menjadi array 1 dimensi (Bukan DataFrame Kolom Ganda)
        open_arr = data_saham['Open'].to_numpy().flatten()
        high_arr = data_saham['High'].to_numpy().flatten()
        low_arr = data_saham['Low'].to_numpy().flatten()
        close_arr = data_saham['Close'].to_numpy().flatten()
        volume_arr = data_saham['Volume'].to_numpy().flatten()

        # Ambil nilai terakhir
        harga_terakhir = float(close_arr[-1])
        harga_sebelumnya = float(close_arr[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100
        
        # Hitung Rata-rata Volume 20 Hari
        vol_series = pd.Series(volume_arr)
        vol_avg = float(vol_series.rolling(window=20).mean().iloc[-1])

        # Hitung Pivot Support & Resistance (Data 5 Hari Terakhir)
        high_5h = float(max(high_arr[-5:]))
        low_5h = float(min(low_arr[-5:]))
        pivot = (high_5h + low_5h + harga_terakhir) / 3
        r1 = (2 * pivot) - low_5h
        r2 = pivot + (high_5h - low_5h)
        s1 = (2 * pivot) - high_5h
        s2 = pivot - (high_5h - low_5h)

        # Layout Tampilan Atas (3 Kolom Metrik)
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN SAHAM", f"{ticker_clean}", "Status: Terhubung Aktif")
        col_m2.metric("HARGA CLOSE TERAKHIR", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME TRANSAKSI", f"{volume_arr[-1]/1e6:.1f} M", f"Rata-rata 20H: {vol_avg/1e6:.1f} M", delta_color="off")

        st.markdown("---")
        col_left, col_right = st.columns([1, 1.2])

        with col_left:
            st.subheader("🏹 TRADING PLAN SETUP")
            st.info(f"🛒 **BUY AREA:** Rp {int(s1):,.0f} - Rp {int(harga_terakhir):,.0f}")
            st.error(f"⚠️ **STOP LOSS (SL):** Rp {int(s2 * 0.99):,.0f}")
            st.success(f"🎯 **TARGET UNTUNG:** TP1: Rp {int(r1):,.0f} | TP2: Rp {int(r2):,.0f}")
            
            st.write("---")
            st.subheader("📊 STATISTIK HARIAN KUNCI")
            st.write(f"• Harga Pembukaan Hari Ini: **Rp {float(open_arr[-1]):,.0f}**")
            st.write(f"• Harga Tertinggi Hari Ini: **Rp {float(high_arr[-1]):,.0f}**")
            st.write(f"• Harga Terendah Hari Ini: **Rp {float(low_arr[-1]):,.0f}**")

        with col_right:
            st.subheader("📊 ANALISIS GRAFIK CANDLESTICK HARIAN")
            # Menampilkan 40 candle terakhir agar chart rapi dan tidak blur
            idx_data = data_saham.index[-40:]
            fig = go.Figure(data=[go.Candlestick(
                x=idx_data, open=open_arr[-40:], high=high_arr[-40:],
                low=low_arr[-40:], close=close_arr[-40:], name='Candle'
            )])
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=350)
            st.plotly_chart(fig, use_container_width=True)
            
            # --- SEKSI INFO DIVIDEN DOMESTIK ---
            st.write("---")
            st.subheader("💰 DETEKTOR SENTIMEN DIVIDEN TERBARU (2026)")
            if dividen_lokal["ada"]:
                st.markdown(f"""
                <div style="background-color: #1f2937; padding: 15px; border-radius: 8px; border-left: 5px solid #10B981;">
                    <h5 style="margin:0; color:#10B981;">📢 Berita / Agenda RUPS & Dividen Terdeteksi</h5>
                    <p style="margin:8px 0; color:white; font-size:14px;">🔗 <a href="{dividen_lokal['link']}" target="_blank" style="color:#FBBF24; text-decoration:none; font-weight:bold;">{dividen_lokal['judul']}</a></p>
                    <caption style="color:#9ca3af; font-size:12px;">Sumber: {dividen_lokal['sumber']}</caption>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("⚪ Belum mendeteksi berita atau pengumuman jadwal dividen krusial di media nasional baru-baru ini.")

            # --- SEKSI BERITA MULTI-SOURCE ---
            st.write("---")
            st.subheader("📰 AGREGATOR BERITA & SENTIMEN LOKAL (ID)")
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔗 **[{item['title']}]({item['link']})**")
                    st.caption(f"📰 {item['source']} | 🕒 {item['date']}")
                    st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
            else:
                st.info(f"⚪ Tidak ditemukan berita spesifik Bahasa Indonesia untuk kata kunci '{ticker_clean}' saat ini.")
    else:
        st.error(f"Gagal menarik data! Pastikan kode '{ticker_clean}' terdaftar di Bursa Efek Indonesia.")

except Exception as e:
    st.error(f"Aplikasi mengalami gangguan teknis: {str(e)}")
