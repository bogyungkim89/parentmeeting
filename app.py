import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime, timedelta

# ==========================================
# 1. 데이터베이스 초기화 및 설정
# ==========================================
DB_NAME = "school_consultation.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 관리자 설정 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS admin_settings (id INTEGER PRIMARY KEY, notice TEXT)''')
    # 허용된 교사 이메일 목록
    c.execute('''CREATE TABLE IF NOT EXISTS allowed_teachers (email TEXT PRIMARY KEY)''')
    # 교사 정보
    c.execute('''CREATE TABLE IF NOT EXISTS teachers (email TEXT PRIMARY KEY, name TEXT, grade TEXT, class_num TEXT)''')
    # 교사 설정 (상담 시간 단위, 학부모 안내문구)
    c.execute('''CREATE TABLE IF NOT EXISTS teacher_settings (email TEXT PRIMARY KEY, duration INTEGER, notice TEXT)''')
    # 학생 정보
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_email TEXT, grade TEXT, class_num TEXT, 
                 student_num TEXT, name TEXT, stu_id TEXT, free_time TEXT)''')
    # 교사 가능 시간
    c.execute('''CREATE TABLE IF NOT EXISTS availability (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_email TEXT, avail_date TEXT, start_time TEXT, end_time TEXT)''')
    # 예약 내역
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_email TEXT, stu_id TEXT, parent_name TEXT, phone TEXT, 
                 book_date TEXT, start_time TEXT, end_time TEXT)''')
    conn.commit()
    conn.close()

# ==========================================
# 2. 헬퍼 함수
# ==========================================
def run_query(query, params=(), fetch=True):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        result = c.fetchall()
    else:
        conn.commit()
        result = None
    conn.close()
    return result

def generate_time_blocks(start_str, end_str, duration_mins):
    """시작시간과 종료시간 사이에서 지정된 분 단위의 상담 블록을 10분 단위 간격으로 생성"""
    start = datetime.strptime(start_str, '%H:%M')
    end = datetime.strptime(end_str, '%H:%M')
    blocks = []
    
    current = start
    while current + timedelta(minutes=duration_mins) <= end:
        block_end = current + timedelta(minutes=duration_mins)
        blocks.append(f"{current.strftime('%H:%M')} ~ {block_end.strftime('%H:%M')}")
        current += timedelta(minutes=10) # 10분 단위로 선택지 제공
    return blocks

# ==========================================
# 3. 전체 관리자 페이지
# ==========================================
def admin_page():
    st.header("전체 관리자 페이지")
    
    st.subheader("1. 교사 등록 허용 이메일 관리")
    st.write("이 예약 시스템을 사용할 수 있는 교사의 구글 이메일을 등록합니다.")
    new_email = st.text_input("허용할 교사 이메일 (구글 계정)")
    if st.button("이메일 등록"):
        if new_email:
            try:
                run_query("INSERT INTO allowed_teachers (email) VALUES (?)", (new_email,), fetch=False)
                st.success(f"{new_email} 등록 완료")
            except sqlite3.IntegrityError:
                st.warning("이미 등록된 이메일입니다.")
                
    allowed = run_query("SELECT email FROM allowed_teachers")
    if allowed:
        st.write("등록된 이메일 목록:", [e[0] for e in allowed])

    st.divider()
    st.subheader("2. 교사 안내 문구 설정")
    admin_notice = st.text_area("교사들이 시스템 접속 시 볼 수 있는 안내 문구를 작성해주세요.")
    if st.button("안내 문구 저장"):
        run_query("DELETE FROM admin_settings", fetch=False)
        run_query("INSERT INTO admin_settings (id, notice) VALUES (1, ?)", (admin_notice,), fetch=False)
        st.success("저장되었습니다.")

# ==========================================
# 4. 교사 페이지
# ==========================================
def teacher_page():
    st.header("교사 페이지")
    
    # 관리자 안내 문구 노출
    admin_settings = run_query("SELECT notice FROM admin_settings WHERE id=1")
    if admin_settings and admin_settings[0][0]:
        st.info(f"**[관리자 안내사항]**\n{admin_settings[0][0]}")

    email = st.text_input("교사 이메일 입력 (구글 계정)")
    if not email:
        st.stop()

    allowed = run_query("SELECT email FROM allowed_teachers WHERE email=?", (email,))
    if not allowed:
        st.error("관리자로부터 승인되지 않은 이메일입니다. 전체 관리자에게 문의하세요.")
        st.stop()

    teacher_info = run_query("SELECT * FROM teachers WHERE email=?", (email,))
    
    if not teacher_info:
        st.subheader("교사 초기 등록")
        name = st.text_input("성명")
        grade = st.text_input("학년")
        class_num = st.text_input("반")
        if st.button("교사 등록 완료"):
            run_query("INSERT INTO teachers (email, name, grade, class_num) VALUES (?, ?, ?, ?)", 
                      (email, name, grade, class_num), fetch=False)
            run_query("INSERT INTO teacher_settings (email, duration, notice) VALUES (?, 20, '')", (email,), fetch=False)
            st.success("등록이 완료되었습니다. 화면을 새로고침 해주세요.")
            st.rerun()
        st.stop()

    st.success(f"{teacher_info[0][1]} 선생님, 환영합니다! ({teacher_info[0][2]}학년 {teacher_info[0][3]}반 독립 관리 페이지)")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["기본 설정", "상담 가능 시간", "학생 명단 관리", "예약 내역 조회", "예약 내역 다운로드"])

    # --- 1. 기본 설정 (상담 단위, 학부모 문구) ---
    with tab1:
        st.subheader("상담 설정")
        current_settings = run_query("SELECT duration, notice FROM teacher_settings WHERE email=?", (email,))
        curr_duration = current_settings[0][0] if current_settings else 20
        curr_notice = current_settings[0][1] if current_settings else ""

        duration = st.radio("1회 상담 시간 단위", [20, 30], index=0 if curr_duration == 20 else 1)
        notice = st.text_area("학부모 예약 완료 화면에 노출할 안내 문구 (장소, 유의사항 등)", value=curr_notice)
        
        if st.button("설정 저장"):
            run_query("UPDATE teacher_settings SET duration=?, notice=? WHERE email=?", (duration, notice, email), fetch=False)
            st.success("설정이 저장되었습니다.")

    # --- 2. 상담 가능 시간 ---
    with tab2:
        st.subheader("상담 가능 시간 등록 (10분 단위 설정)")
        avail_date = st.date_input("가능한 연도/월/일 선택")
        
        col1, col2 = st.columns(2)
        # 10분 단위 시간 생성을 위한 리스트
        time_options = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(8, 22) for m in (0, 10, 20, 30, 40, 50)]
        with col1:
            start_time = st.selectbox("시작 시간", time_options)
        with col2:
            end_time = st.selectbox("종료 시간", time_options, index=12)

        if st.button("가능 시간 추가"):
            run_query("INSERT INTO availability (teacher_email, avail_date, start_time, end_time) VALUES (?, ?, ?, ?)",
                      (email, str(avail_date), start_time, end_time), fetch=False)
            st.success("추가되었습니다.")
            
        st.write("등록된 가능 시간 목록")
        avails = run_query("SELECT id, avail_date, start_time, end_time FROM availability WHERE teacher_email=?", (email,))
        if avails:
            df_avails = pd.DataFrame(avails, columns=["ID", "일자", "시작시간", "종료시간"])
            st.dataframe(df_avails)

    # --- 3. 학생 명단 관리 ---
    with tab3:
        st.subheader("학생 데이터 엑셀 업로드")
        
        # 템플릿 다운로드
        df_template = pd.DataFrame(columns=["학년", "반", "번호", "이름", "학번", "공강시간"])
        towrite = io.BytesIO()
        df_template.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button("엑셀 양식 다운로드", towrite, "student_template.xlsx", 
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.caption("※ 공강시간 입력 예시: 월 10:00-11:00, 수 14:00-15:00")

        uploaded_file = st.file_uploader("학생 정보 엑셀 파일 업로드", type=["xlsx"])
        if uploaded_file is not None:
            df_students = pd.read_excel(uploaded_file)
            if st.button("학생 데이터 DB 저장"):
                run_query("DELETE FROM students WHERE teacher_email=?", (email,), fetch=False) # 기존 데이터 초기화
                for _, row in df_students.iterrows():
                    run_query("INSERT INTO students (teacher_email, grade, class_num, student_num, name, stu_id, free_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (email, str(row['학년']), str(row['반']), str(row['번호']), str(row['이름']), str(row['학번']), str(row['공강시간'])), fetch=False)
                st.success("학생 데이터가 성공적으로 업로드 되었습니다.")
                
        current_students = run_query("SELECT grade, class_num, student_num, name, stu_id, free_time FROM students WHERE teacher_email=?", (email,))
        if current_students:
            st.dataframe(pd.DataFrame(current_students, columns=["학년", "반", "번호", "이름", "학번", "공강시간"]))

    # --- 4. 예약 내역 조회 및 변경 ---
    with tab4:
        st.subheader("학부모 상담 예약 접수 내역")
        bookings = run_query("""
            SELECT b.id, s.grade, s.class_num, s.student_num, s.stu_id, s.name, b.parent_name, b.book_date, b.start_time, b.end_time 
            FROM bookings b JOIN students s ON b.stu_id = s.stu_id 
            WHERE b.teacher_email=? ORDER BY b.book_date, b.start_time
        """, (email,))
        
        if bookings:
            df_bookings = pd.DataFrame(bookings, columns=["예약ID", "학년", "반", "번호", "학번", "학생명", "학부모명", "일자", "시작", "종료"])
            st.dataframe(df_bookings)
            
            del_id = st.text_input("삭제할 예약 ID 입력")
            if st.button("예약 내역 삭제"):
                run_query("DELETE FROM bookings WHERE id=?", (del_id,), fetch=False)
                st.success("삭제되었습니다.")
                st.rerun()
        else:
            st.write("접수된 예약이 없습니다.")

    # --- 5. 예약 내역 다운로드 (요청하신 포맷 적용) ---
    with tab5:
        st.subheader("예약 내역 엑셀 다운로드")
        if bookings:
            export_data = []
            for b in bookings:
                # b: ID(0), 학년(1), 반(2), 번호(3), 학번(4), 학생명(5), 학부모명(6), 일자(7), 시작(8), 종료(9)
                date_obj = datetime.strptime(b[7], "%Y-%m-%d")
                weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]
                time_format = f"{date_obj.strftime('%m/%d')}({weekday_kr}) {b[8]}~{b[9]}"
                
                export_data.append({
                    "A (공란)": "", "학년": b[1], "반": b[2], "번호": b[3], "학번": b[4],
                    "학생명": b[5], "G (공란)": "", "학부모명": b[6], "상담 월/일(요일) 시간": time_format
                })
            
            df_export = pd.DataFrame(export_data)
            
            output = io.BytesIO()
            df_export.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button("맞춤형 예약 데이터 엑셀 다운로드", output, "consultation_schedule.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==========================================
# 5. 학부모 (예약자) 페이지
# ==========================================
def parent_page():
    st.header("학부모 상담 예약")
    
    stu_name = st.text_input("자녀 이름")
    stu_id = st.text_input("고유 학번")
    
    if st.button("학생 정보 조회") or st.session_state.get('verified', False):
        student = run_query("SELECT teacher_email, free_time FROM students WHERE name=? AND stu_id=?", (stu_name, stu_id))
        
        if not student:
            st.error("일치하는 학생 정보가 없습니다. 이름과 학번을 확인해주세요.")
            return
            
        st.session_state.verified = True
        teacher_email = student[0][0]
        free_time_info = student[0][1]
        
        st.success(f"{stu_name} 학생 확인 완료. 담당 선생님의 일정표를 불러옵니다.")
        st.info(f"학생 공강 시간 정보: {free_time_info}")
        
        settings = run_query("SELECT duration, notice FROM teacher_settings WHERE email=?", (teacher_email,))
        duration_mins = settings[0][0] if settings else 20
        teacher_notice = settings[0][1] if settings else ""
        
        st.subheader("상담 날짜 및 시간 선택")
        selected_date = st.date_input("상담 희망일 선택")
        
        # 교사의 해당 일자 가능 시간 조회
        avails = run_query("SELECT start_time, end_time FROM availability WHERE teacher_email=? AND avail_date=?", 
                           (teacher_email, str(selected_date)))
        
        if not avails:
            st.warning("선택하신 날짜에 담당 교사의 상담 가능 일정이 없습니다.")
            return
            
        # 해당 학급의 기예약된 시간 가져오기 (교차 및 중복 예약 방지)
        booked = run_query("SELECT start_time, end_time FROM bookings WHERE teacher_email=? AND book_date=?", 
                           (teacher_email, str(selected_date)))
        booked_times = [f"{b[0]} ~ {b[1]}" for b in booked]

        # 교사의 전체 가능 시간 범위 내에서 시간 블록 생성
        all_blocks = []
        for avail in avails:
            blocks = generate_time_blocks(avail[0], avail[1], duration_mins)
            all_blocks.extend(blocks)
            
        # 기예약된 시간 블록 필터링 (완벽히 겹치거나 일부 겹치는 시간 제외)
        available_blocks = [b for b in all_blocks if b not in booked_times]

        if not available_blocks:
            st.warning("선택하신 날짜의 모든 상담 예약이 마감되었습니다.")
            return
            
        st.write(f"담당 교사 설정 상담 단위: {duration_mins}분")
        selected_block = st.selectbox("상담 희망 시간 선택 (학생의 공강시간을 참고하여 선택해주세요)", available_blocks)
        
        st.divider()
        parent_name = st.text_input("학부모 성명")
        parent_phone = st.text_input("학부모 휴대폰 번호")
        
        if st.button("예약 확정"):
            if not parent_name or not parent_phone:
                st.error("성명과 연락처를 모두 입력해주세요.")
                return
                
            start_t, end_t = selected_block.split(" ~ ")
            run_query("INSERT INTO bookings (teacher_email, stu_id, parent_name, phone, book_date, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (teacher_email, stu_id, parent_name, parent_phone, str(selected_date), start_t, end_t), fetch=False)
            
            st.success("예약이 확정되었습니다!")
            st.info(f"**[담당 교사 안내사항]**\n{teacher_notice}")
            
            # 예약 완료 후 상태 초기화 (재예약 방지)
            st.session_state.verified = False

# ==========================================
# 앱 메인 실행부
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="학부모 상담 예약 시스템", layout="wide")
    init_db()
    
    st.sidebar.title("메뉴")
    role = st.sidebar.radio("접속 권한을 선택하세요", ["학부모 (예약자)", "교사", "전체 관리자"])
    
    if role == "전체 관리자":
        admin_page()
    elif role == "교사":
        teacher_page()
    else:
        parent_page()
