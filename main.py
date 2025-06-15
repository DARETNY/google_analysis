from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from deep_translator import GoogleTranslator
from google_play_scraper import reviews_all

# --- 1. Sayfa Konfigürasyonu ---
st.set_page_config(
    page_title="Racing Kingdom Analiz Paneli",
    page_icon="🏁",  # Yarış bayrağı ikonu
    layout="wide"
)

# --- 2. Ana Başlık ve Açıklama ---
st.title("🏁 Racing Kingdom: Android Yorum Analiz Paneli")
st.markdown(
    "Bu panel, **Racing Kingdom** oyununun Google Play Store'daki oyuncu yorumlarını analiz etmek, "
    "genel memnuniyeti ölçmek ve performansı görselleştirmek için tasarlanmıştır."
)
st.markdown("---")

# --- 3. Sabitler ---
GOOGLE_PLAY_ID = 'com.supergears.racingkingdom'


# --- 4. Veri Çekme ve İşleme Fonksiyonu ---
@st.cache_data(ttl="8h", show_spinner="Yorum verileri çekiliyor, lütfen bekleyin...")
def fetch_and_process_reviews(selected_countries_iso, perform_translation):
    """
    Yorumları çeker ve sadece istenirse çeviri yapar.
    """
    all_reviews_list = []
    fetch_time = datetime.now()

    for country_iso in selected_countries_iso:
        try:
            gp_reviews = reviews_all(
                GOOGLE_PLAY_ID, lang=country_iso, country=country_iso
            )
            for r in gp_reviews:
                all_reviews_list.append({
                    'Kullanıcı Adı': r.get('userName'), 'Yorum': r.get('content'),
                    'Puan': r.get('score'), 'Tarih': r.get('at'),
                    'Ülke': country_iso.upper(), 'Geliştirici Yanıtı': r.get('replyContent'),
                    'Uygulama Versiyonu': r.get('appVersion')
                })
        except Exception as e:
            st.warning(f"'{country_iso}' kodu için yorum çekilirken bir sorun oluştu: {e}")
            pass

    if not all_reviews_list:
        return pd.DataFrame(), fetch_time

    df = pd.DataFrame(all_reviews_list)
    df.dropna(subset=['Yorum', 'Puan'], inplace=True)
    df = df[df['Yorum'].str.strip() != '']
    df['Tarih'] = pd.to_datetime(df['Tarih']).dt.tz_localize(None)

    if perform_translation:
        translator = GoogleTranslator(target='tr')

        def get_translation(row):
            if row['Ülke'].lower() == 'tr' or not isinstance(row['Yorum'], str) or not row['Yorum'].strip():
                return None
            try:
                return translator.translate(row['Yorum'])
            except Exception:
                return "Çeviri Hatası"

        df['Yorum (TR Çeviri)'] = df.apply(get_translation, axis=1)
    else:
        df['Yorum (TR Çeviri)'] = None

    df = df.sort_values(by='Tarih', ascending=False)
    df = df.drop_duplicates(subset=['Kullanıcı Adı', 'Yorum', 'Tarih'], keep='first')

    df = df[[
        'Tarih', 'Ülke', 'Kullanıcı Adı', 'Puan', 'Uygulama Versiyonu',
        'Yorum', 'Yorum (TR Çeviri)', 'Geliştirici Yanıtı'
    ]]

    return df, fetch_time


# --- 5. Arayüz (Sidebar) ---
st.sidebar.header("🛠️ Analiz Ayarları")
country_input = st.sidebar.text_input(
    "Analiz Edilecek Ülke Kodları",
    "gb, us, de, tr",
    help="Google Play ülke kodlarını girin. Örneğin: Türkiye için 'tr', Amerika için 'us'."
)

translate_option = st.sidebar.checkbox(
    "Yorumları Türkçe'ye Çevir (Yavaşlatır)"
)

if translate_option:
    st.sidebar.warning(
        "Otomatik çeviri aktif. Bu işlem, yorum sayısına bağlı olarak "
        "analiz süresini uzatabilir."
    )

selected_iso_codes = [code.strip().lower() for code in country_input.split(',') if code.strip()]

if st.sidebar.button("📊 Raporu Oluştur", type="primary", use_container_width=True):
    if not selected_iso_codes:
        st.error("Lütfen en az bir ülke kodu girin.")
    else:
        df_reviews, last_fetch_time = fetch_and_process_reviews(
            tuple(sorted(selected_iso_codes)),
            perform_translation=translate_option
        )
        st.session_state['df_reviews'] = df_reviews
        st.session_state['last_fetch_time'] = last_fetch_time

# --- 6. Sonuçların Gösterilmesi ---
if 'df_reviews' not in st.session_state:
    st.info("Başlamak için sol menüden ayarları yapıp 'Raporu Oluştur' butonuna tıklayın.")
else:
    df_reviews = st.session_state['df_reviews']
    last_fetch_time = st.session_state['last_fetch_time']

    if df_reviews.empty:
        st.warning("Girilen ülke kodları için yorum bulunamadı. Kodları kontrol edip tekrar deneyin.")
    else:
        st.success(
            f"**Pist Raporu Hazır!** Seçilen {df_reviews['Ülke'].nunique()} ülkeden toplam **{len(df_reviews):,}** benzersiz yorum incelendi."
        )

        # Metrikler
        st.header("🏆 Genel Metrikler", divider='rainbow')
        col1, col2, col3 = st.columns(3)
        avg_rating = df_reviews['Puan'].mean()
        col1.metric("Ortalama Oyuncu Puanı", f"{avg_rating:.2f} ⭐")
        col2.metric("Toplam Yorum Sayısı", f"{len(df_reviews):,}")
        col3.metric("Analiz Edilen Ülke Sayısı", f"{df_reviews['Ülke'].nunique()}")

        # Görselleştirmeler
        st.header("📈 Görsel Analizler", divider='rainbow')
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("Ülkelere Göre Yorum Hacmi")
            country_counts = df_reviews['Ülke'].value_counts()
            fig_country_dist = px.bar(
                country_counts, x=country_counts.index, y=country_counts.values,
                labels={'x': 'Ülke Kodu', 'y': 'Yorum Sayısı'}, color=country_counts.index,
                text_auto=True
            )
            fig_country_dist.update_layout(showlegend=False)
            st.plotly_chart(fig_country_dist, use_container_width=True)

        with col_chart2:
            st.subheader("Ülke Derecelendirmeleri")
            country_avg_rating = df_reviews.groupby('Ülke')['Puan'].mean().sort_values(ascending=False)
            fig_country_rating = px.bar(
                country_avg_rating, x=country_avg_rating.index, y=country_avg_rating.values,
                labels={'x': 'Ülke Kodu', 'y': 'Ortalama Puan'}, color=country_avg_rating.index,
                text=[f'{p:.2f} ⭐' for p in country_avg_rating.values]
            )
            fig_country_rating.update_layout(showlegend=False, yaxis_range=[0, 5.5])
            st.plotly_chart(fig_country_rating, use_container_width=True)

        st.subheader("Haftalık Yorum Trendi")
        df_time = df_reviews.set_index('Tarih').resample('W').agg(
            Yorum_Sayısı=('Yorum', 'count'),
            Ortalama_Puan=('Puan', 'mean')
        ).dropna()
        st.line_chart(df_time)

        # Ham Veri Tablosu
        with st.expander("📝 Detaylı Yorum İncelemesi ve Filtreleme"):
            st.dataframe(df_reviews, use_container_width=True, height=500)
            st.info(f"**{len(df_reviews):,}** benzersiz yorum görüntüleniyor.")
            csv = df_reviews.drop(columns=['Ülke']).to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="⬇️ Görüntülenen Veriyi CSV Olarak İndir",
                data=csv,
                file_name=f"RacingKingdom_Yorum_Analizi_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
