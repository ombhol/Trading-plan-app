import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
import requests
import urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Trading Plan Pro - 100% Data Resmi BEI", page_icon="📈", layout="wide")

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

st.title("🦅 DASHBOARD TRADING PLAN HARIAN & AGREGATOR BERITA")
st.write(f"Analisis Pasar Terintegrasi 100% Data Resmi BEI (Situs IDX) & Google News — Update: {date.today().strftime('%d %B %Y')}")

ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BBCA").upper()

st.markdown("---")

# --- FUNGSI 1: AMBIL DATA HARGA & RINGKASAN SAHAM DARI BEI ---
def ambil_data_saham_bei(ticker):
    url = "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
    params = {"culture": "id-id", "pageNumber": 1, "pageSize": 20, "keyword": ticker}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=7)
        res_data = res.json()
        if res_data and "data" in res_data and len(res_data["data"]) > 0:
            # Cari data yang kodenya benar-benar cocok (exact match)
            for item in res_data["data"]:
                if item.get("StockCode") == ticker:
                    return {"sukses": True, "data": item}
    except Exception as e:
        pass
    return {"sukses": False}

# --- FUNGSI 2: AMBIL JADWAL DIVIDEN DARI BEI ---
def ambil_dividen_bei(ticker):
    url = "https://www.idx.co.id/primary/CorporateAction/GetCorporateActionTrading"
    params = {"culture": "id-id", "pageNumber": 1, "pageSize": 50, "keyword": ticker}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=7)
        res_data = res.json()
        if res_data and "data" in res_data and len(res_data["data"]) > 0:
            df = pd.DataFrame(res_data["data"])
            df_div = df[df['Jumlah'].str.contains('Dividen|Cash', case=False, na=False)]
            if not df_div.empty:
                terbaru = df_div.iloc[0]
                
                def format_tgl(s):
                    if not s or s == '-': return '-'
                    try: return pd.to_datetime(s[:10]).strftime('%d %B %Y')
                    except: return s
                
                return {
                    "ada": True,
                    "nominal": terbaru.get('Jumlah', '-'),
                    "cum_date": format_tgl(terbaru.get('CumDateReg')),
                    "ex_date": format_tgl(terbaru.get('ExDateReg')),
                    "Keterangan": terbaru.get('Keterangan', '-')
                }
    except:
        pass
    return {"ada": False}

# --- FUNGSI 3: AMBIL BERITA INDONESIA ---
def ambil_berita_indonesia(ticker):
    daftar_berita = []
    try:
        query = urllib.parse.quote(f"{ticker} saham")
        url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            root = ET.fromstring(response.read())
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            if " - " in title: title = title.rsplit(" - ", 1)[0]
            daftar_berita.append({"title": title, "link": item.find('link').text, "source": item.find('source').text, "date": item.find('pubDate').text[:16]})
    except: pass
    return daftar_berita

# --- PROSES UTAMA ---
try:
    with st.spinner('Menghubungkan langsung ke API Bursa Efek Indonesia (IDX)...'):
        hasil_saham = ambil_data_saham_bei(ticker_input)
        data_dividen_bei = ambil_dividen_bei(ticker_input)
        berita_lokal = ambil_berita_indonesia(ticker_input)
        
    if hasil_saham["sukses"]:
        s_data = hasil_saham["data"]
        
        # Ekstrak metrik dari data BEI
        harga_terakhir = float(s_data.get("Close", 0))
        harga_tertinggi = float(s_data.get("High", 0))
        harga_terendah = float(s_data.get("Low", 0))
        harga_pembukaan = float(s_data.get("Open", 0))
        harga_sebelumnya = float(s_data.get("Prev", 0))
        volume_transaksi = float(s_data.get("Volume", 0))
        perubahan = float(s_data.get("Change", 0))
        
        # Hitung persentase perubahan secara mandiri
        persentase_ubah = (perubahan / harga_sebelumnya) * 100 if harga_sebelumnya > 0 else 0.0

        # Strategi S&R Klasik menggunakan data harian berjalan dari BEI
        pivot = (harga_tertinggi + harga_terendah + harga_terakhir) / 3
        r1 = (2 * pivot) - harga_terendah
        r2 = pivot + (harga_tertinggi - harga_terendah)
        s1 = (2 * pivot) - harga_tertinggi
        s2 = pivot - (harga_tertinggi - harga_terendah)

        # Layout Tampilan 3 Kolom Utama Atas
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN SAHAM (IDX)", f"{ticker_input}", "SUMBER: ASLI BEI")
        col_m2.metric("HARGA TERAKHIR", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME HARIAN", f"{volume_transaksi/1e6:.2f} M lembar", f"Nilai: Rp {float(s_data.get('Value', 0))/1e9:.2f} Miliar", delta_color="off")

        st.markdown("---")
        col_left, col_right = st.columns([1, 1.2])

        with col_left:
            st.subheader("🏹 TRADING PLAN SETUP")
            st.info(f"🛒 **BUY AREA:** Rp {int(s1):,.0f} - Rp {int(harga_terakhir):,.0f}")
            st.error(f"⚠️ **STOP LOSS (SL):** Rp {int(s2 * 0.99):,.0f}")
            st.success(f"🎯 **TARGET UNTUNG:** TP1: Rp {int(r1):,.0f} | TP2: Rp {int(r2):,.0f}")
            
            st.write("---")
            st.subheader("📊 RINGKASAN TRANSAKSI BEI HARI INI")
            st.write(f"• **Harga Pembukaan:** Rp {harga_pembukaan:,.0f}")
            st.write(f"• **Rentang Harian:** Rp {harga_terendah:,.0f} - Rp {harga_tertinggi:,.0f}")
            st.write(f"• **Frekuensi Transaksi:** {float(s_data.get('Frequency', 0)):,.0f} kali")

        with col_right:
            st.subheader("📊 GRAFIK INTRA-DAY/HARIAN BERJALAN")
            # Membuat visualisasi bar rentang harga hari ini berdasarkan data resmi bursa
            fig = go.Figure(data=[go.Candlestick(
                x=[date.today().strftime('%Y-%m-%d')],
                open=[harga_pembukaan],
                high=[harga_tertinggi],
                low=[harga_terendah],
                close=[harga_terakhir],
                name='Rentang Hari Ini'
            )])
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            # --- SEKSI DATA RESMI BURSA EFEK INDONESIA (BEI) ---
            st.write("---")
            st.subheader("💰 INFO AKSI KORPORASI / DIVIDEN (SUMBER: BEI)")
            if data_dividen_bei["ada"]:
                st.markdown(f"""
                <div style="background-color: #1f2937; padding: 15px; border-radius: 8px; border-left: 5px solid #10B981;">
                    <h4 style="margin:0; color:#10B981;">📢 Pengumuman Dividen Terakhir / Terjadwal</h4>
                    <p style="margin:5px 0 0 0; color:white;"><b>Keterangan:</b> {data_dividen_bei['nominal']}</p>
                    <table style="width:100%; margin-top:10px; color:white;">
                        <tr><td><b>📅 CUM DATE (Pasar Reguler):</b></td><td style="color:#FBBF24;"><b>{data_dividen_bei['cum_date']}</b></td></tr>
                        <tr><td><b>📅 EX DATE (Pasar Reguler):</b></td><td style="color:#EF4444;"><b>{data_dividen_bei['ex_date']}</b></td></tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("⚪ Tidak ada pengumuman agenda dividen tunai terbaru yang tercatat di papan keterbukaan informasi IDX saat ini.")

            # --- SEKSI BERITA ---
            st.write("---")
            st.subheader("📰 BERITA & SENTIMEN PASAR LOKAL")
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔗 **[{item['title']}]({item['link']})**")
                    st.caption(f"📰 {item['source']} | 🕒 {item['date']}")
            else:
                st.info("⚪ Tidak ada berita terbaru.")
    else:
        st.error(f"Kode Saham '{ticker_input}' tidak ditemukan atau tidak aktif di sistem Bursa Efek Indonesia.")
except Exception as e:
    st.error(f"Sistem Error: {str(e)}")
