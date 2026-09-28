import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timezone

st.set_page_config(
    page_title="Trading Panel",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
[data-testid="stMetricValue"] {
    font-size: 1.35rem;
}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def get_data(symbol, period, interval):
    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            c[0] if isinstance(c, tuple) else c
            for c in df.columns
        ]

    required = ["Open", "High", "Low", "Close", "Volume"]

    for column in required:
        if column not in df.columns:
            return pd.DataFrame()

    df = df[required].dropna().copy()

    return df


def prepare_4h(df):
    if df.empty:
        return df

    result = df.resample("4h").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()

    return result


def add_indicators(df):
    data = df.copy()

    data["ATR"] = (
        data["High"] - data["Low"]
    ).rolling(14).mean()

    data["Resistance"] = (
        data["High"]
        .rolling(20)
        .max()
        .shift(1)
    )

    data["Support"] = (
        data["Low"]
        .rolling(20)
        .min()
        .shift(1)
    )

    data["Breakout"] = (
        data["Close"] > data["Resistance"]
    )

    data["HH"] = (
        data["High"] > data["High"].shift(1)
    )

    data["HL"] = (
        data["Low"] > data["Low"].shift(1)
    )

    data["LH"] = (
        data["High"] < data["High"].shift(1)
    )

    data["LL"] = (
        data["Low"] < data["Low"].shift(1)
    )

    return data


def calculate_levels(df):
    last = df.iloc[-1]

    price = float(last["Close"])

    if pd.notna(last["ATR"]):
        atr = float(last["ATR"])
    else:
        atr = max(price * 0.01, 0.01)

    if pd.notna(last["Resistance"]):
        resistance = float(last["Resistance"])
    else:
        resistance = price + atr

    if pd.notna(last["Support"]):
        support = float(last["Support"])
    else:
        support = price - atr

    breakout = max(resistance, price)

    tp1 = breakout + atr
    tp2 = breakout + atr * 2

    stop = min(
        support,
        price - atr
    )

    return {
        "price": price,
        "breakout": breakout,
        "tp1": tp1,
        "tp2": tp2,
        "stop": stop,
        "atr": atr,
    }


def format_price(value):
    if value >= 1000:
        return f"{value:,.2f}"

    if value >= 1:
        return f"{value:.2f}"

    return f"{value:.6f}"


st.title("📈 Trading Panel")

st.caption(
    "Market data: Yahoo Finance via yfinance • "
    "L2 bölümü simülasyondur."
)


# SIDEBAR

with st.sidebar:

    st.header("Market")

    symbol = st.text_input(
        "Sembol",
        value="BTC-USD",
        help=(
            "Örnek: BTC-USD, ETH-USD, "
            "AAPL, NVDA, TSLA, SPY, ^GSPC"
        ),
    ).strip().upper()

    timeframe = st.selectbox(
        "Zaman Dilimi",
        [
            "1m",
            "5m",
            "15m",
            "1h",
            "4h",
            "1D",
        ],
        index=3,
    )

    if timeframe == "1m":
        period = "1d"
        yf_interval = "1m"

    elif timeframe == "5m":
        period = "5d"
        yf_interval = "5m"

    elif timeframe == "15m":
        period = "1mo"
        yf_interval = "15m"

    elif timeframe == "1h":
        period = "3mo"
        yf_interval = "1h"

    elif timeframe == "4h":
        period = "3mo"
        yf_interval = "1h"

    else:
        period = "2y"
        yf_interval = "1d"

    bars = st.slider(
        "Grafik bar sayısı",
        50,
        500,
        200,
        10,
    )

    refresh = st.button(
        "🔄 Veriyi yenile",
        use_container_width=True,
    )


if refresh:
    st.cache_data.clear()


# DATA

with st.spinner("Piyasa verisi alınıyor..."):

    df = get_data(
        symbol,
        period,
        yf_interval,
    )


if timeframe == "4h" and not df.empty:
    df = prepare_4h(df)


if df.empty:

    st.error(
        "Veri alınamadı. "
        "Sembolü kontrol et veya birkaç saniye sonra tekrar dene."
    )

    st.stop()


df = add_indicators(df)

plot_df = df.tail(bars)

levels = calculate_levels(df)


# PRICE DATA

last_price = float(
    df["Close"].iloc[-1]
)

if len(df) > 1:

    previous_price = float(
        df["Close"].iloc[-2]
    )

else:

    previous_price = last_price


change = (
    last_price - previous_price
)

if previous_price != 0:

    change_percent = (
        change / previous_price * 100
    )

else:

    change_percent = 0


# METRICS

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric(
    "Fiyat",
    format_price(last_price),
)

m2.metric(
    "Değişim",
    f"{change_percent:+.2f}%",
)

m3.metric(
    "Breakout",
    format_price(
        levels["breakout"]
    ),
)

m4.metric(
    "TP1",
    format_price(
        levels["tp1"]
    ),
)

m5.metric(
    "Stop",
    format_price(
        levels["stop"]
    ),
)


# CANDLESTICK CHART

fig = go.Figure()


fig.add_trace(
    go.Candlestick(
        x=plot_df.index,
        open=plot_df["Open"],
        high=plot_df["High"],
        low=plot_df["Low"],
        close=plot_df["Close"],
        name="Price",
    )
)


fig.add_trace(
    go.Scatter(
        x=plot_df.index,
        y=plot_df["Resistance"],
        mode="lines",
        name="Resistance",
        line=dict(
            width=1,
            dash="dot",
        ),
    )
)


fig.add_trace(
    go.Scatter(
        x=plot_df.index,
        y=plot_df["Support"],
        mode="lines",
        name="Support",
        line=dict(
            width=1,
            dash="dot",
        ),
    )
)


# LEVELS

chart_levels = [
    (
        levels["breakout"],
        "Breakout",
        "dash",
    ),
    (
        levels["tp1"],
        "TP1",
        "dot",
    ),
    (
        levels["tp2"],
        "TP2",
        "dot",
    ),
    (
        levels["stop"],
        "Stop Loss",
        "dash",
    ),
]


for value, name, dash in chart_levels:

    fig.add_hline(
        y=value,
        line_dash=dash,
        annotation_text=(
            f"{name}: "
            f"{format_price(value)}"
        ),
    )


fig.update_layout(
    height=620,
    template="plotly_dark",
    xaxis_rangeslider_visible=False,
    margin=dict(
        l=10,
        r=10,
        t=30,
        b=10,
    ),
    legend=dict(
        orientation="h",
        y=1.02,
        x=0,
    ),
)


st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "displaylogo": False
    },
)


# VOLUME

st.subheader("📊 Hacim")


volume_fig = go.Figure()


volume_fig.add_trace(
    go.Bar(
        x=plot_df.index,
        y=plot_df["Volume"],
        name="Volume",
    )
)


volume_fig.update_layout(
    height=220,
    template="plotly_dark",
    margin=dict(
        l=10,
        r=10,
        t=10,
        b=10,
    ),
    showlegend=False,
)


st.plotly_chart(
    volume_fig,
    use_container_width=True,
    config={
        "displaylogo": False
    },
)


# BREAKOUT + LEVELS

col1, col2 = st.columns(2)


with col1:

    st.subheader(
        "🚨 Breakout Durumu"
    )

    if bool(
        df["Breakout"].iloc[-1]
    ):

        st.success(
            "Breakout koşulu oluştu: "
            f"fiyat {format_price(last_price)}"
        )

    else:

        st.info(
            "Henüz breakout koşulu yok. "
            "Referans direnç: "
            f"{format_price(levels['breakout'])}"
        )


with col2:

    st.subheader(
        "📐 Teknik Seviyeler"
    )

    st.write(
        f"**Fiyat:** "
        f"{format_price(levels['price'])}"
    )

    st.write(
        f"**Breakout:** "
        f"{format_price(levels['breakout'])}"
    )

    st.write(
        f"**TP1:** "
        f"{format_price(levels['tp1'])}"
    )

    st.write(
        f"**TP2:** "
        f"{format_price(levels['tp2'])}"
    )

    st.write(
        f"**Stop Loss:** "
        f"{format_price(levels['stop'])}"
    )

    st.caption(
        "Seviyeler basit ATR + "
        "destek/direnç hesabıdır. "
        "Yatırım tavsiyesi değildir."
    )


# MARKET STRUCTURE

st.subheader(
    "📖 Market Structure"
)


structure = []


for index, row in df.tail(8).iterrows():

    labels = []

    if row["HH"]:
        labels.append("HH")

    if row["HL"]:
        labels.append("HL")

    if row["LH"]:
        labels.append("LH")

    if row["LL"]:
        labels.append("LL")

    structure.append(
        {
            "Zaman": index,
            "Close": row["Close"],
            "Yapı": (
                ", ".join(labels)
                if labels
                else "-"
            ),
        }
    )


structure_df = pd.DataFrame(
    structure
)


st.dataframe(
    structure_df,
    use_container_width=True,
    hide_index=True,
)


# SIMULATED ORDER BOOK

st.subheader(
    "📚 Simulated L2 Order Book"
)

st.caption(
    "Bu gerçek borsa emir defteri değildir. "
    "Görsel ve analiz amaçlı basit bir simülasyondur."
)


mid_price = last_price

tick_size = max(
    levels["atr"] / 10,
    mid_price * 0.0005,
)


rng = np.random.default_rng(42)

order_book = []


for i in range(1, 11):

    bid_price = (
        mid_price -
        tick_size * i
    )

    ask_price = (
        mid_price +
        tick_size * i
    )

    bid_size = float(
        rng.integers(
            1,
            100,
        )
    )

    ask_size = float(
        rng.integers(
            1,
            100,
        )
    )

    order_book.append(
        [
            i,
            bid_price,
            bid_size,
            ask_price,
            ask_size,
        ]
    )


book_df = pd.DataFrame(
    order_book,
    columns=[
        "Level",
        "Bid Price",
        "Bid Size",
        "Ask Price",
        "Ask Size",
    ],
)


st.dataframe(
    book_df,
    use_container_width=True,
    hide_index=True,
)


# FOOTER

current_time = datetime.now(
    timezone.utc
).strftime(
    "%Y-%m-%d %H:%M:%S UTC"
)


st.caption(
    f"Son kontrol: {current_time}"
  )
