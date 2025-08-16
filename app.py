import io
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="월별 매출 대시보드", layout="wide")

# =============== Sidebar Controls ===============
st.sidebar.title("데이터/표시 설정")

uploaded = st.sidebar.file_uploader("CSV 업로드 (필수 컬럼: 월, 매출액, 전년동월, 증감률)", type=["csv"])

unit_label_map = {1: "원", 1_000: "천원", 1_000_000: "백만원"}
unit_div = st.sidebar.selectbox("표시 단위", options=list(unit_label_map.keys()),
                                index=2,  # 기본: 백만원
                                format_func=lambda v: unit_label_map[v])

goal = st.sidebar.number_input("연간 목표 매출(원)", value=200_000_000, step=1_000_000)

focus = st.sidebar.selectbox("보기 모드", options=["전체", "추세", "증감률", "누적", "히트맵"])
show_labels = st.sidebar.toggle("데이터 라벨 표시", value=False)

st.sidebar.caption("월 형식 예: 2024-01 · 음수 막대는 패턴으로도 구분")

# =============== Load Data ===============
def load_data(file) -> pd.DataFrame:
    if file is not None:
        df = pd.read_csv(file)
    else:
        # 예시 데이터 (업로드 없을 때 미리보기용)
        df = pd.DataFrame({
            "월": ["2024-01","2024-02","2024-03","2024-04","2024-05","2024-06","2024-07","2024-08","2024-09","2024-10","2024-11","2024-12"],
            "매출액": [12000000,13500000,11000000,18000000,21000000,19000000,17500000,22000000,24000000,20000000,23000000,25000000],
            "전년동월": [10500000,11200000,12800000,15200000,18500000,17000000,16000000,20000000,21500000,19800000,21000000,23500000],
            "증감률":   [14.3,20.5,-14.1,18.4,13.5,11.8,9.4,10.0,11.6,1.0,9.5,6.4]
        })
    # 기본 검증
    need = ["월", "매출액", "전년동월", "증감률"]
    for c in need:
        if c not in df.columns:
            raise ValueError(f"필수 컬럼 누락: {c}")

    # 정제 및 정렬
    df = df.copy()
    df["월"] = df["월"].astype(str).str.strip()
    df["매출액"] = pd.to_numeric(df["매출액"], errors="coerce")
    df["전년동월"] = pd.to_numeric(df["전년동월"], errors="coerce")
    # "10.5%" 같은 입력도 허용
    df["증감률"] = pd.to_numeric(df["증감률"].astype(str).str.replace("%", "", regex=False), errors="coerce")

    df = df.dropna(subset=["월", "매출액", "전년동월", "증감률"])
    # YYYY-MM 문자열 정렬을 가정
    df = df.sort_values("월").reset_index(drop=True)

    # 파생
    df["매출액_단위"] = df["매출액"] / unit_div
    df["전년동월_단위"] = df["전년동월"] / unit_div
    df["누적매출"] = df["매출액"].cumsum()
    df["누적매출_단위"] = df["누적매출"] / unit_div
    return df

try:
    df = load_data(uploaded)
    has_data = True
except Exception as e:
    has_data = False
    st.error(f"데이터 로드 오류: {e}")

st.title("월별 매출 대시보드")

if not has_data:
    st.stop()

# KPI 계산
max_sales = df["매출액"].max()
avg_sales = df["매출액"].mean()
avg_rate = df["증감률"].mean()
cum_last = df["누적매출"].iloc[-1]
goal_pct = (cum_last / goal * 100) if goal > 0 else np.nan

unit_name = unit_label_map[unit_div]

# =============== KPI Row ===============
col1, col2, col3, col4 = st.columns(4)
col1.metric("최고 매출", f"{max_sales/unit_div:,.1f} {unit_name}")
col2.metric("평균 매출", f"{avg_sales/unit_div:,.1f} {unit_name}")
col3.metric("평균 증감률", f"{avg_rate:,.1f} %")
col4.metric("누적/목표", f"{cum_last/unit_div:,.1f} / {goal/unit_div:,.1f} {unit_name}",
            delta=f"달성률 {goal_pct:,.1f}%" if goal > 0 else "목표 미설정")

# 공통 테마 레이아웃
def layout_xy(y_title):
    return dict(
        margin=dict(t=50, r=20, b=50, l=60),
        xaxis=dict(title="월", tickangle=-45),
        yaxis=dict(title=y_title),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

# PNG 다운로드 헬퍼
def fig_download_button(fig, filename, key):
    try:
        buf = fig.to_image(format="png", engine="kaleido", width=1200, height=700)
        st.download_button("PNG 저장", data=buf, file_name=f"{filename}.png",
                           mime="image/png", key=key)
    except Exception as e:
        st.info("PNG 저장을 위해 `kaleido`가 필요합니다. 설치 후 다시 시도해주세요.")
        st.code("pip install -U kaleido")

# =============== Charts ===============
def line_sales_vs_prev():
    # 최대/최소 강조
    max_idx = int(df["매출액"].idxmax())
    min_idx = int(df["매출액"].idxmin())

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["월"], y=df["매출액_단위"], mode="lines+markers+text" if show_labels else "lines+markers",
        name="당해 매출", text=[f"{v:,.0f}" if show_labels else "" for v in df["매출액_단위"]],
        textposition="top center"
    ))
    fig.add_trace(go.Scatter(
        x=df["월"], y=df["전년동월_단위"], mode="lines+markers+text" if show_labels else "lines+markers",
        name="전년동월 매출", text=[f"{v:,.0f}" if show_labels else "" for v in df["전년동월_단위"]],
        textposition="top center"
    ))
    fig.add_trace(go.Scatter(
        x=[df.loc[max_idx, "월"]], y=[df.loc[max_idx, "매출액_단위"]],
        mode="markers+text", name="최대",
        marker=dict(size=14, symbol="star", color="#10b981"),
        text=["최대"], textposition="bottom center"
    ))
    fig.add_trace(go.Scatter(
        x=[df.loc[min_idx, "월"]], y=[df.loc[min_idx, "매출액_단위"]],
        mode="markers+text", name="최소",
        marker=dict(size=12, symbol="x", color="#ef4444"),
        text=["최소"], textposition="bottom center"
    ))
    fig.update_layout(title=f"월별 매출 vs 전년동월 · 단위: {unit_name}", **layout_xy(f"매출액({unit_name})"))
    return fig

def bar_rate():
    colors = ["#10b981" if v >= 0 else "#ef4444" for v in df["증감률"]]
    patterns = ["" if v >= 0 else "/" for v in df["증감률"]]
    fig = go.Figure(go.Bar(
        x=df["월"], y=df["증감률"],
        marker=dict(color=colors, pattern=dict(shape=patterns)),
        text=[f"{v:.1f}%" if show_labels else "" for v in df["증감률"]],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>"
    ))
    fig.update_layout(title="월별 증감률(%)", **layout_xy("증감률(%)"))
    return fig

def cum_with_goal():
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["월"], y=df["누적매출_단위"],
        mode="lines+markers+text" if show_labels else "lines+markers",
        name="누적 매출",
        text=[f"{v:,.0f}" if show_labels else "" for v in df["누적매출_단위"]],
        textposition="top center"
    ))
    if goal and goal > 0:
        fig.add_trace(go.Scatter(
            x=[df["월"].iloc[0], df["월"].iloc[-1]],
            y=[goal / unit_div, goal / unit_div],
            mode="lines", name="목표", line=dict(dash="dash")
        ))
    fig.update_layout(title=f"누적 매출 추이 · 단위: {unit_name}", **layout_xy(f"누적 매출({unit_name})"))
    return fig

def heat_rate():
    fig = go.Figure(data=go.Heatmap(
        x=df["월"], y=["증감률"], z=[df["증감률"]],
        colorscale=[[0, "#ef4444"], [0.5, "#f8fafc"], [1, "#10b981"]],
        showscale=True, hovertemplate="%{x} · %{z:.1f}%<extra></extra>"
    ))
    fig.update_layout(title="증감률 히트맵", margin=dict(t=50, r=20, b=50, l=60))
    return fig

# =============== Rendering by Focus ===============
if focus in ("전체", "추세"):
    c1, c2 = st.columns((2, 1))
    with c1:
        fig1 = line_sales_vs_prev()
        st.plotly_chart(fig1, use_container_width=True)
        fig_download_button(fig1, "line_sales_vs_prev", key="dl1")
    if focus == "추세":
        st.stop()

if focus in ("전체", "증감률"):
    fig2 = bar_rate()
    st.plotly_chart(fig2, use_container_width=True)
    fig_download_button(fig2, "bar_rate", key="dl2")
    if focus == "증감률":
        st.stop()

if focus in ("전체", "누적"):
    fig3 = cum_with_goal()
    st.plotly_chart(fig3, use_container_width=True)
    fig_download_button(fig3, "cum_with_goal", key="dl3")
    if focus == "누적":
        st.stop()

if focus in ("전체", "히트맵"):
    fig4 = heat_rate()
    st.plotly_chart(fig4, use_container_width=True)
    fig_download_button(fig4, "heat_rate", key="dl4")

# =============== Data Preview ===============
with st.expander("데이터 미리보기 / 기술통계"):
    st.write(df[["월", "매출액", "전년동월", "증감률"]])
    st.write("기술통계 (매출액):")
    st.write(df["매출액"].describe().to_frame().T)
