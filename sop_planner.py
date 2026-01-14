import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="Production Scheduler Pro", layout="wide")

st.title("🏭 CCL 생산 공정 최적화 시뮬레이터")
st.markdown("""
현장 데이터를 기반으로 **Changeover Loss(색상 교체 시간)**를 최소화하는 스케줄을 제안합니다.
**기존 방식(FCFS)**과 **최적화 방식(Optimization)**의 효율을 시각적으로 비교합니다.
""")

# ---------------------------------------------------------
# 2. 사이드바: 현실적인 생산 조건 설정
# ---------------------------------------------------------
st.sidebar.header("⚙️ 라인 조건 설정 (Line Constraints)")

# 실제 현업 변수: 라인 속도와 교체 시간
line_speed = st.sidebar.slider("평균 라인 속도 (톤/시간)", 10, 50, 20)
setup_time = st.sidebar.number_input("색상 교체 소요 시간 (분)", value=60)

# ---------------------------------------------------------
# 3. 데이터 로딩 (샘플 데이터도 현실적으로 하드코딩)
# ---------------------------------------------------------
# 파일 업로드가 없을 경우 사용할 '진짜 같은' 예제 데이터
default_data = {
    '주문번호': ['ORD-101', 'ORD-102', 'ORD-103', 'ORD-104', 'ORD-105', 'ORD-106', 'ORD-107', 'ORD-108'],
    '고객사': ['LG전자', '삼성전자', '현대차', '기아', '포스코E&C', 'LG하우시스', '삼성물산', 'KG모빌리티'],
    '강종/색상': ['White', 'Blue', 'White', 'Red', 'Blue', 'White', 'Red', 'Blue'], # 뒤죽박죽 섞임
    '주문량(톤)': [100, 50, 80, 40, 60, 120, 30, 50],
    '폭(mm)': [1200, 1000, 1200, 900, 1000, 1200, 900, 1000]
}

uploaded_file = st.sidebar.file_uploader("생산 계획 엑셀 업로드", type=['xlsx', 'csv'])

if uploaded_file:
    df_raw = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
else:
    df_raw = pd.DataFrame(default_data)

# ---------------------------------------------------------
# 4. 핵심 로직: 스케줄링 계산 함수 (엔진)
# ---------------------------------------------------------
def calculate_schedule(df, is_optimized=False):
    # 최적화 모드면 '색상' -> '폭' 순서로 정렬 (그룹핑)
    if is_optimized:
        # 1차: 색상별 묶기, 2차: 폭이 넓은 순에서 좁은 순으로 (광협 스케줄링)
        schedule = df.sort_values(by=['강종/색상', '폭(mm)'], ascending=[True, False]).copy()
    else:
        # 비최적화면 그냥 들어온 순서대로
        schedule = df.copy()
    
    # 시간 계산
    start_time = datetime(2026, 1, 10, 8, 0) # 오늘 오전 8시 시작
    schedule_list = []
    
    last_color = None
    
    for idx, row in schedule.iterrows():
        # 1. 준비 교체 시간 (Setup) 계산
        current_setup = 0
        is_changeover = False
        
        if last_color is not None and row['강종/색상'] != last_color:
            current_setup = setup_time # 색이 바뀌면 60분 청소
            is_changeover = True
        
        # 교체 작업(로스) 블록 추가
        if is_changeover:
            schedule_list.append({
                '작업명': 'Changeover (교체)',
                '색상': 'Setup (Loss)', # 차트 색깔용
                '시작': start_time,
                '종료': start_time + timedelta(minutes=current_setup),
                '상세': f"{last_color} -> {row['강종/색상']}"
            })
            start_time = start_time + timedelta(minutes=current_setup)
            
        # 2. 실제 생산 시간 계산 (톤 / 속도)
        # 속도(톤/시간)를 분당 생산량으로 환산
        production_minutes = (row['주문량(톤)'] / line_speed) * 60
        end_time = start_time + timedelta(minutes=production_minutes)
        
        # 생산 작업 블록 추가
        schedule_list.append({
            '작업명': f"{row['주문번호']} ({row['강종/색상']})",
            '색상': row['강종/색상'], # 실제 제품 색상
            '시작': start_time,
            '종료': end_time,
            '상세': f"{row['고객사']} / {row['주문량(톤)']}톤"
        })
        
        start_time = end_time
        last_color = row['강종/색상']
        
    return pd.DataFrame(schedule_list)

# ---------------------------------------------------------
# 5. 시뮬레이션 실행 및 시각화
# ---------------------------------------------------------

# (1) 기존 방식 (AS-IS)
df_asis = calculate_schedule(df_raw, is_optimized=False)

# (2) 최적화 방식 (TO-BE)
df_tobe = calculate_schedule(df_raw, is_optimized=True)

# 결과 비교 메트릭
loss_asis = df_asis[df_asis['작업명'] == 'Changeover (교체)']['종료'].count() * setup_time
loss_tobe = df_tobe[df_tobe['작업명'] == 'Changeover (교체)']['종료'].count() * setup_time
time_saved = loss_asis - loss_tobe

st.subheader("📊 시뮬레이션 결과 요약")
col1, col2, col3 = st.columns(3)
col1.metric("기존 방식 총 교체시간", f"{loss_asis} 분", "비효율 발생")
col2.metric("최적화 후 교체시간", f"{loss_tobe} 분", f"▼ {time_saved}분 절감")
col3.metric("가동 효율 개선", f"+{(time_saved/(loss_asis if loss_asis>0 else 1))*100:.1f}%")

st.divider()

# 차트 그리기 함수
def draw_gantt(df, title):
    fig = px.timeline(
        df, x_start="시작", x_end="종료", y="색상", 
        color="색상",
        hover_data=['작업명', '상세'],
        title=title,
        height=300,
        # 회색(Loss)과 실제 제품 색상 매칭
        color_discrete_map={
            'Setup (Loss)': '#555555', # 진회색
            'White': '#f0f0f0', 
            'Blue': '#1f77b4', 
            'Red': '#d62728'
        }
    )
    fig.update_yaxes(categoryorder='array', categoryarray=['Setup (Loss)', 'White', 'Blue', 'Red'])
    fig.update_layout(
        xaxis_title="시간 (Time)", 
        yaxis_title="작업 유형",
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor='rgba(0,0,0,0)' # 배경 투명하게
    )
    return fig

# 탭으로 구분해서 보여주기
tab1, tab2 = st.tabs(["🔴 기존 방식 (Before)", "🟢 최적화 방식 (After)"])

with tab1:
    st.caption("주문이 들어온 순서대로 생산했을 때의 모습입니다. 회색(Loss) 구간이 중간중간 발생합니다.")
    st.plotly_chart(draw_gantt(df_asis, "AS-IS 생산 스케줄 (Before)"), use_container_width=True)

with tab2:
    st.caption("동일 색상끼리 묶고(Grouping), 폭 순서(광협)까지 고려하여 재배열한 모습입니다.")
    st.plotly_chart(draw_gantt(df_tobe, "TO-BE 생산 스케줄 (After)"), use_container_width=True)

# 데이터 테이블 표시
with st.expander("📋 상세 데이터 확인하기"):
    st.dataframe(df_raw)