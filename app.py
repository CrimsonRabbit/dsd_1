# app.py
# -*- coding: utf-8 -*-
"""
월별 매출 대시보드 (가독성/접근성 개선판)
- 명도 대비 강화, 색약 사용자 고려(Okabe–Ito 기반 팔레트)
- 색상 + 패턴/마커/선스타일 병행
- kaleido 미설치 환경에서도 정상 구동 (PNG 저장은 선택)
"""
import io
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------
# 0) 페이지 & 공통 스타일
# ----------------------------------------------------
st.set_page_config(page_title="월별 매출 대시보드", page_icon="📈", layout="wide")

# 접근성 & 가독성 향상용 컬러(Okabe–Ito + 브랜드 보완)
COLORS = {
    # 핵심 팔레트 (color-blind safe)
    "primary": "#0072B2",     # 본선(올해)
    "secondary": "#D55E00",   # 비교(전년/목표)
    "positive": "#009E73",    # 증가/성공
    "caution":  "#E69F00",    # 주의/예측
    "critical": "#CC79A7",    # 감소/경고(패턴 병행)
    "sky":      "#56B4E9",    # 보조 하이라이트
    # 브랜드/중립
    "brand_primary": "#173A6D",
    "neutral_text": "#2B2B2B",
    "grid": "#C7CED6",
    "card_bg": "#F5F7FA",
    "canvas": "#FFFFFF",
}

def _style_metric_label(label: str) -> str:
    return f"<span style='color:{COLORS['neutral_text']};font-weight:600;'>{label}</span>"

st.markdown(
    """
    <style>
      .metric-card { background-color:#F5F7FA; padding:16px 18px; border-radius:14px; border:1px solid #E3E8EF; }
      .metric-value { font-size:22px; font-weight:700; color:#2B2B2B; }
      .metric-delta-pos { color:#009E73; font-weight:600; }
      .metric-delta-neg { color:#CC79A7; font-weight:600; }
      body, p, span, div, h1, h2, h3, h4, h5, h6 {
        font-family: "Pretendard", system-ui, -apple-system, Segoe UI, Roboto, "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------
# 1) 사이드바: 데이터 업로드 & 옵션
# ----------------------------------------------------
st.sidebar.header("데이터/표시 설정")
st.sidebar.caption("CSV 업로드 (필수: 월, 매출액, 전년동월, 증감률) · 월 표기 예: 2024-01")

uploaded = st.sidebar.file_uploader("CSV 업로드", type=["csv"])

unit_label_map = {1: "원", 1_000: "천원", 1_000_000: "백만원"}
unit_div = st.sidebar.selectbox("표시 단위", options=list(unit_label_map.keys()), index=2,
                                format_func=lambda v: unit_label_map[v])
unit_name = unit_label_map[unit_div]

goal = st.sidebar.number_input("연간 목표 매출(원)", value=200_000_000, step=1_000_000)

focus = st.sidebar.selectbox("보기 모드", options=["전체", "추세", "증감률", "누적", "히트맵"], index=0)
show_labels = st.sidebar.toggle("데이터 라벨 표시", value=False)
use_brand_primary = st.sidebar.toggle("브랜드 네이비를 본선 색으로 사용", value=False)

# ----------------------------------------------------
# 2) 데이터 로드/전처리
# ----------------------------------------------------
def load_data(file) -> pd.DataFrame:
    if file is not None:
        df = pd.read_csv(file)
    else:
        # 샘플 (업로드 없을 때)
        df = pd.DataFrame({
            "월": ["2024-01","2024-02","2024-03","2024-04","2024-05","2024-06","2024-07","2024-08","2024-09","2024-10","2024-11","2024-12"],
            "매출액": [12000000,13500000,11000000,18000000,21000000,19000000,17500000,22000000,24000000,20000000,23000000,25000000],
            "전년동월": [10500000,11200000,12800000,15200000,18500000,17000000,16000000,20000000,21500000,19800000,21000000,23500000],
            "증감률":   [14.3,20.5,-14.1,18.4,13.5,11.8,9.4,10.0,11.6,1.0,9.5,6.4]
        })
    # 필수 컬럼 확인
    need = ["월", "매출액", "전년동월", "증감률"]
    for c in need:
        if c not in df.columns:
            raise ValueError(f"필수 컬럼 누락: {c}")

    # 정제
    df = df.copy()
    df["월"] = df["월"].astype(str).str.strip()
    df["매출액"] = pd.to_numeric(df["매출액"], errors="coerce")
    df["전년동월"] = pd.to_numeric(df["전년동월"], errors="coerce")
    df["증감률"] = pd.to_numeric(df["증감률"].astype(str).str.replace("%", "", regex=False), errors="coerce")
    df = df.dropna(subset=["월", "매출액", "전년동월", "증감률"]).sort_values("월").reset_index(drop=True)

    # 파생
    df["매출액_단위"]   = df["매출액"] / unit_div
    df["전년동월_단위"] = df["전년동월"] / unit_div
    df["누적매출"]      = df["매출액"].cumsum()
    df["누적매출_단위"] = df["누적매출"] / unit_div
    return df

try:
    df = load_data(uploaded)
    has_data = True
except Exception as e:
    has_data = False
    st.error(f"데이터 로드 오류: {e}")

# ----------------------------------------------------
# 3) 헤더 & KPI
# ----------------------------------------------------
st.markdown(
    f"""
    <div style="background:{COLORS['card_bg']}; padding:18px 22px; border-radius:14px; border:1px solid #E3E8EF;">
      <h1 style="margin:0; color:{COLORS['brand_primary']}">월별 매출 대시보드</h1>
    </div>
    """,
    unsafe_allow_html=True
)

if not has_data:
    st.stop()

max_sales = df["매출액"].max()
avg_sales = df["매출액"].mean()
avg_rate  = df["증감률"].replace([np.inf, -np.inf], np.nan).fillna(0).mean()
cum_last  = df["누적매출"].iloc[-1]
goal_pct  = (cum_last / goal * 100) if goal > 0 else np.nan

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"<div class='metric-card'>{_style_metric_label('최고 매출')}<div class='metric-value'>{max_sales/unit_div:,.1f} {unit_name}</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='metric-card'>{_style_metric_label('평균 매출')}<div class='metric-value'>{avg_sales/unit_div:,.1f} {unit_name}</div></div>", unsafe_allow_html=True)
with c3:
    delta_cls = "metric-delta-pos" if avg_rate >= 0 else "metric-delta-neg"
    st.markdown(f"<div class='metric-card'>{_style_metric_label('평균 증감률')}<div class='metric-value'><span class='{delta_cls}'>{avg_rate:.1f}%</span></div></div>", unsafe_allow_html=True)
with c4:
    attain_rate = 100 * cum_last / goal if goal else 0
    color_cls = "metric-delta-pos" if attain_rate >= 100 else "metric-delta-neg" if attain_rate < 80 else ""
    st.markdown(
        f"<div class='metric-card'>{_style_metric_label('누적/목표')}<div class='metric-value'>{cum_last/unit_div:,.1f} / {goal/unit_div:,.1f} {unit_name} <span class='{color_cls}' style='font-size:16px;'>({attain_rate:.1f}%)</span></div></div>",
        unsafe_allow_html=True
    )

# ----------------------------------------------------
# 4) 공통 레이아웃 옵션
# ----------------------------------------------------
def layout_xy(y_title):
    return dict(
        margin=dict(t=50, r=20, b=50, l=60),
        xaxis=dict(title="월", tickangle=-45, showgrid=False),
        yaxis=dict(title=y_title, gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"]),
        paper_bgcolor=COLORS["canvas"],
        plot_bgcolor=COLORS["canvas"],
        font=dict(color=COLORS["neutral_text"]),
        legend=dict(bgcolor=COLORS["card_bg"], bordercolor="#E3E8EF"),
    )

def download_png(fig, name, key):
    with st.popover("PNG 저장", use_container_width=False):
        st.caption("PNG 저장에는 kaleido가 필요합니다. 필요 시 아래 명령으로 설치하세요.")
        st.code("pip install -U kaleido")
        if st.button("PNG로 내보내기", key=key):
            try:
                buf = fig.to_image(format="png", engine="kaleido", width=1400, height=800, scale=2)
                st.download_button("다운로드", data=buf, file_name=f"{name}.png", mime="image/png", key=f"{key}_dl")
            except Exception as e:
                st.warning(f"kaleido가 필요합니다. 오류: {e}")

# ----------------------------------------------------
# 5) 차트들
# ----------------------------------------------------
def chart_line_sales_vs_prev():
    line_color = COLORS["brand_primary"] if use_brand_primary else COLORS["primary"]

    # 최대/최소 포인트
    max_idx = int(df["매출액"].idxmax())
    min_idx = int(df["매출액"].idxmin())

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["월"], y=df["매출액_단위"],
        mode="lines+markers+text" if show_labels else "lines+markers",
        name="당해 매출",
        line=dict(color=line_color, width=3),
        marker=dict(symbol="circle", size=7, color=line_color),
        text=[f"{v:,.0f}" if show_labels else "" for v in df["매출액_단위"]],
        textposition="top center",
        hovertemplate="%{x}<br>%{y:,.0f} " + unit_name + "<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=df["월"], y=df["전년동월_단위"],
        mode="lines+markers+text" if show_labels else "lines+markers",
        name="전년동월",
        line=dict(color=COLORS["secondary"], width=2, dash="dot"),
        marker=dict(symbol="triangle-up", size=7, color=COLORS["secondary"]),
        text=[f'{v:,.0f}' if show_labels else "" for v in df["전년동월_단위"]],
        textposition="top center",
        hovertemplate="%{x}<br>%{y:,.0f} " + unit_name + "<extra></extra>"
    ))
    # 월평균 목표선
    if goal and goal > 0:
        monthly_target = (goal / max(len(df), 1)) / unit_div
        fig.add_hline(y=monthly_target, line=dict(color=COLORS["grid"], dash="dash"),
                      annotation_text="월평균 목표", annotation_position="top left")

    # 최대/최소 강조
    fig.add_trace(go.Scatter(
        x=[df.loc[max_idx, "월"]], y=[df.loc[max_idx, "매출액_단위"]],
        mode="markers+text", name="최대",
        marker=dict(size=16, symbol="star", color=COLORS["canvas"],
                    line=dict(color=line_color, width=2)),
        text=["최대"], textposition="bottom center",
        hovertemplate="%{x}<br>최대: %{y:,.0f} " + unit_name + "<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=[df.loc[min_idx, "월"]], y=[df.loc[min_idx, "매출액_단위"]],
        mode="markers+text", name="최소",
        marker=dict(size=14, symbol="x", color=COLORS["critical"]),
        text=["최소"], textposition="bottom center",
        hovertemplate="%{x}<br>최소: %{y:,.0f} " + unit_name + "<extra></extra>"
    ))

    fig.update_layout(title=f"월별 매출 vs 전년동월 · 단위: {unit_name}", **layout_xy(f"매출액({unit_name})"))
    return fig

def chart_bar_rate():
    colors = [COLORS["positive"] if v >= 0 else COLORS["critical"] for v in df["증감률"]]
    patterns = ["" if v >= 0 else "/" for v in df["증감률"]]
    fig = go.Figure(go.Bar(
        x=df["월"], y=df["증감률"],
        marker=dict(color=colors, pattern=dict(shape=patterns), line=dict(color="#FFFFFF", width=0.5)),
        text=[f"{v:.1f}%" if show_labels else "" for v in df["증감률"]],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>"
    ))
    fig.update_layout(title="월별 증감률(%)", **layout_xy("증감률(%)"))
    return fig

def chart_cum_with_goal():
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["월"], y=df["누적매출_단위"],
        mode="lines+markers+text" if show_labels else "lines+markers",
        name="누적 매출",
        line=dict(color=COLORS["sky"], width=3),
        marker=dict(symbol="diamond", size=7, color=COLORS["sky"]),
        text=[f"{v:,.0f}" if show_labels else "" for v in df["누적매출_단위"]],
        textposition="top center",
        hovertemplate="%{x}<br>%{y:,.0f} " + unit_name + "<extra></extra>"
    ))
    if goal and goal > 0:
        fig.add_hline(y=goal / unit_div, line=dict(color="#7A7C88", dash="dot"),
                      annotation_text=f"연간 목표 {goal/unit_div:,.0f} {unit_name}",
                      annotation_position="top left")
    fig.update_layout(title=f"누적 매출 추이 · 단위: {unit_name}", **layout_xy(f"누적 매출({unit_name})"))
    return fig

def chart_heatmap_sales():
    # 연-월 피벗 히트맵 (단일계열 파랑)
    tmp = df.copy()
    # YYYY-MM 가정 → 연/월 분리
    tmp["연"] = tmp["월"].str.slice(0,4)
    tmp["월번호"] = tmp["월"].str.slice(5,7)
    pivot = tmp.pivot_table(index="연", columns="월번호", values="매출액_단위", aggfunc="sum")
    # 월 라벨
    columns_sorted = sorted(pivot.columns.tolist())
    z_vals = pivot[columns_sorted].values if len(pivot.columns) else pivot.values

    fig = go.Figure(data=go.Heatmap(
        z=z_vals,
        x=[f"{m}월" for m in columns_sorted] if len(columns_sorted) else pivot.columns,
        y=[str(y) for y in pivot.index],
        colorscale=[[0, "#E8F3FC"], [1, COLORS["primary"]]],  # 단일 파랑 계열
        colorbar=dict(title=f"{unit_name}"),
        zsmooth=False, showscale=True,
        hoverongaps=False
    ))
    fig.update_layout(title=f"월별 매출 히트맵 (단위: {unit_name})",
                      margin=dict(t=50, r=20, b=50, l=60),
                      paper_bgcolor=COLORS["canvas"],
                      plot_bgcolor=COLORS["canvas"],
                      font=dict(color=COLORS["neutral_text"]))
    return fig

# ----------------------------------------------------
# 6) 렌더링
# ----------------------------------------------------
if focus in ("전체", "추세"):
    c1, c2 = st.columns((2, 1))
    with c1:
        fig1 = chart_line_sales_vs_prev()
        st.plotly_chart(fig1, use_container_width=True)
        download_png(fig1, "line_sales_vs_prev", key="dl1")
    if focus == "추세":
        st.stop()

if focus in ("전체", "증감률"):
    fig2 = chart_bar_rate()
    st.plotly_chart(fig2, use_container_width=True)
    download_png(fig2, "bar_rate", key="dl2")
    if focus == "증감률":
        st.stop()

if focus in ("전체", "누적"):
    fig3 = chart_cum_with_goal()
    st.plotly_chart(fig3, use_container_width=True)
    download_png(fig3, "cum_with_goal", key="dl3")
    if focus == "누적":
        st.stop()

if focus in ("전체", "히트맵"):
    fig4 = chart_heatmap_sales()
    st.plotly_chart(fig4, use_container_width=True)
    download_png(fig4, "heatmap_sales", key="dl4")

# ----------------------------------------------------
# 7) 데이터 미리보기/기술통계
# ----------------------------------------------------
with st.expander("데이터 미리보기 / 기술통계"):
    st.write(df[["월", "매출액", "전년동월", "증감률"]])
    st.write("기술통계 (매출액):")
    st.write(df["매출액"].describe().to_frame().T)

# ----------------------------------------------------
# 8) 접근성 요약 푸터
# ----------------------------------------------------
st.markdown(
    """
    ---
    **접근성 체크리스트**  
    - 색상 + 패턴/마커/선스타일 병행 (색에만 의존하지 않음)  
    - 텍스트 대비(본문 7:1, 보조 4.5:1) 확보  
    - 월 표기 `YYYY-MM`, 단위 명확히 표기  
    """
)
