# dashboard_app.py — 삼성전기 주가 & 블로그 언급 빈도 대시보드
# 실행: streamlit run dashboard_app.py

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

# ── 설정 ─────────────────────────────────────────────────────────
ROOT            = Path(__file__).parent
DATE_START = date(2024, 6, 1)
DATE_END   = date(2026, 5, 31)

def blog_counts_csv(name: str) -> Path:
    return ROOT / "data" / "processed" / f"blog_counts_{name}.csv"

def available_stocks() -> list[str]:
    """blog_counts_*.csv 파일에서 수집된 종목명 목록 반환"""
    proc = ROOT / "data" / "processed"
    return sorted(
        p.stem.replace("blog_counts_", "")
        for p in proc.glob("blog_counts_*.csv")
    )

st.set_page_config(
    page_title="삼성전기 대시보드",
    page_icon="📈",
    layout="wide",
)

# ── 데이터 로드 (캐시) ────────────────────────────────────────────

@st.cache_data
def load_blog_counts(name: str) -> pd.Series:
    csv = blog_counts_csv(name)
    if not csv.exists():
        return pd.Series(0, index=pd.date_range(str(DATE_START), str(DATE_END), freq="D"), dtype=int)
    df       = pd.read_csv(csv, parse_dates=["date"])
    series   = df.set_index("date")["count"]
    full_idx = pd.date_range(str(DATE_START), str(DATE_END), freq="D")
    return series.reindex(full_idx, fill_value=0)


@st.cache_data
def load_price(yahoo_ticker: str) -> pd.Series:
    df    = yf.download(yahoo_ticker, start=str(DATE_START), end="2026-06-01",
                         auto_adjust=True, progress=False)
    price = df["Close"].squeeze().dropna()
    price.index = price.index.tz_localize(None)
    full_idx = pd.date_range(str(DATE_START), str(DATE_END), freq="D")
    return price.reindex(full_idx).ffill()


# ── 사이드바: 날짜 범위 선택 ─────────────────────────────────────

with st.sidebar:
    st.header("📊 종목 선택")
    stocks = available_stocks()
    if not stocks:
        st.warning("수집된 종목 없음")
        st.stop()
    sel_name = st.selectbox("종목", options=stocks)
    st.divider()
    st.header("📅 기간 설정")
    sel_start, sel_end = st.slider(
        "조회 기간",
        min_value=DATE_START,
        max_value=DATE_END,
        value=(DATE_START, DATE_END),
        format="YYYY-MM-DD",
    )
    st.caption(f"{sel_start} ~ {sel_end}")
    st.divider()
    st.header("📡 데이터 소스")
    sources = st.multiselect(
        "소스 선택",
        options=["네이버 블로그"],
        default=["네이버 블로그"],
    )
    st.divider()
    st.caption("삼성전기 (009150)\n주가 & 블로그 추천 언급 빈도")

# ── 데이터 로드 & 필터링 ─────────────────────────────────────────

with st.spinner("데이터 로딩 중..."):
    blog_all  = load_blog_counts(sel_name)
    meta      = config.load_stocks_meta()
    yahoo_ticker = meta.get(sel_name, {}).get("yahoo_ticker", f"{sel_name}.KS")
    price_all = load_price(yahoo_ticker)

s = pd.Timestamp(sel_start)
e = pd.Timestamp(sel_end)

price    = price_all[s:e]
blog_raw = blog_all[s:e]

# 선택된 데이터 소스의 카운트 합산 (추후 소스 추가 시 여기에 병합)
blog = blog_raw if "네이버 블로그" in sources else pd.Series(
    0, index=blog_raw.index, dtype=int
)

# ── 헤더 ─────────────────────────────────────────────────────────

st.title("📈 삼성전기 (009150) 대시보드")
st.caption(f"수정주가 & 네이버 블로그 추천 언급 빈도 | {sel_start} ~ {sel_end}")

# 요약 지표
col1, col2, col3, col4 = st.columns(4)
start_price = price.dropna().iloc[0]  if not price.dropna().empty else float("nan")
end_price   = price.dropna().iloc[-1] if not price.dropna().empty else float("nan")
col1.metric("조회 시작가", f"{start_price:,.0f}원" if start_price == start_price else "N/A")
col2.metric("조회 종료가", f"{end_price:,.0f}원"   if end_price == end_price   else "N/A",
            delta=f"{end_price - start_price:+,.0f}원" if start_price == start_price and end_price == end_price else None)
col3.metric("블로그 언급 총합", f"{int(blog.sum()):,}건")
col4.metric("일 평균 언급", f"{blog.mean():.1f}건")

st.divider()

# ── 차트 모드 선택 ────────────────────────────────────────────────

from datetime import timedelta

chart_mode = st.radio(
    "차트 모드",
    ["통합 (이중 Y축)", "분리 (상단: 주가 / 하단: 언급 수)"],
    horizontal=True,
)

period_days = (sel_end - sel_start).days
x_end = sel_end + timedelta(days=int(period_days * 0.1))
COMMON_XAXIS = dict(
    showgrid=True, gridcolor="#e5e5e5",
    tickformat="%Y-%m", dtick="M1", fixedrange=True,
    range=[str(sel_start), str(x_end)],
)

# ── 분리 모드 ─────────────────────────────────────────────────────
if chart_mode.startswith("분리"):  # 분리 모드
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.65, 0.35],
        subplot_titles=("수정주가 (원)", "일별 네이버 블로그 추천 언급 수 (건)"),
    )
    fig.add_trace(go.Scatter(
        x=price.index, y=price.values,
        mode="lines", name="수정종가",
        line=dict(color="#1f77b4", width=1.5),
        fill="tozeroy", fillcolor="rgba(31,119,180,0.07)",
        hovertemplate="%{x|%Y-%m-%d}<br>종가: %{y:,.0f}원<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=blog.index, y=blog.values,
        name="네이버 블로그 추천 언급", marker_color="#5b9bd5",
        hovertemplate="%{x|%Y-%m-%d}<br>언급 수: %{y}건<extra></extra>",
    ), row=2, col=1)
    if blog.mean() > 0:
        fig.add_hline(
            y=blog.mean(), row=2, col=1,
            line=dict(color="gray", dash="dash", width=1),
            annotation_text=f"평균 {blog.mean():.1f}건",
            annotation_position="top left", annotation_font_size=11,
        )
    fig.update_layout(
        height=650, showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0),
        hovermode="x unified", dragmode=False,
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=12), margin=dict(t=60, b=40, l=70, r=30),
    )
    fig.update_xaxes(**COMMON_XAXIS)
    fig.update_yaxes(showgrid=True, gridcolor="#e5e5e5",
                     tickformat=",", autorange=True, fixedrange=True, row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#e5e5e5",
                     autorange=True, rangemode="tozero", fixedrange=True, row=2, col=1)

# ── 통합 모드 (이중 Y축) ─────────────────────────────────────────
else:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=blog.index, y=blog.values,
        name="블로그 추천 언급", marker_color="#5b9bd5", opacity=0.6,
        hovertemplate="%{x|%Y-%m-%d}<br>언급 수: %{y}건<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=price.index, y=price.values,
        mode="lines", name="수정종가",
        line=dict(color="#d62728", width=1.8),
        hovertemplate="%{x|%Y-%m-%d}<br>종가: %{y:,.0f}원<extra></extra>",
    ), secondary_y=True)
    if blog.mean() > 0:
        fig.add_hline(
            y=blog.mean(), secondary_y=False,
            line=dict(color="gray", dash="dash", width=1),
            annotation_text=f"평균 {blog.mean():.1f}건",
            annotation_position="top left", annotation_font_size=11,
        )
    fig.update_layout(
        height=550, showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0),
        hovermode="x unified", dragmode=False,
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=12), margin=dict(t=60, b=40, l=70, r=80),
        title=dict(text="수정주가 & 네이버 블로그 추천 언급 수", font=dict(size=14)),
    )
    fig.update_xaxes(**COMMON_XAXIS)
    fig.update_yaxes(
        title_text="블로그 언급 수 (건)", showgrid=True, gridcolor="#e5e5e5",
        rangemode="tozero", autorange=True, fixedrange=True, secondary_y=False,
    )
    fig.update_yaxes(
        title_text="수정주가 (원)", tickformat=",", showgrid=False,
        autorange=True, fixedrange=True, secondary_y=True,
    )

st.plotly_chart(fig, use_container_width=True)
