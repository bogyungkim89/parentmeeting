import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime, timedelta

# ==========================================
# 1. 데이터베이스 초기화 (is_approved 컬럼 추가)
# ==========================================
DB_NAME = "school_consultation.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS admin_settings (id INTEGER PRIMARY KEY, notice TEXT)''')
    # 교사 정보에 is_approved(승인 여부: 0 대기, 1 승인) 추가
    c.execute('''CREATE TABLE IF NOT EXISTS teachers (
                 email TEXT PRIMARY KEY, name TEXT, grade TEXT, class_num TEXT, is_approved INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS teacher_settings (email TEXT PRIMARY KEY, duration INTEGER, notice TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_email TEXT, grade TEXT, class_num TEXT, 
                 student_num TEXT, name TEXT, stu_id TEXT, free_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS availability (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_email TEXT, avail_date TEXT, start_time TEXT, end_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_email TEXT, stu_id TEXT, parent_name TEXT, phone TEXT, 
                 book_date TEXT, start_time TEXT, end_time TEXT)''')
    conn.commit()
    conn.close()

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
    start = datetime.strptime(start_str, '%H:%M')
    end = datetime.strptime(end_str, '%H:%M')
    blocks = []
    current = start
    while current + timedelta(minutes=duration_mins) <= end:
        block_end = current + timedelta(minutes=duration_mins)
        blocks.append(f"{current.strftime('%H:%M')} ~ {block_end.strftime('%H:%M')}")
        current += timedelta(minutes=10)
    return blocks

def go_home():
    st.session_state.page = 'home'
    st.rerun()

# ==========================================
# 2. 메인 홈 화면 (라우팅)
# ==========================================
def home_page():
    st.title("학부모 상담 예약 시스템")
    st.write("### 접속하실 역할을 선택해주세요.")
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("자녀의 상담 시간을 예약합니다.")
        if st.button("👩‍👧 학부모 (예약자) 접속", use_container_width=True):
            st.session_state.page = 'parent'
            st.rerun()
    with col2:
        st.success("학생 등록 및 예약 관리를 합니다.")
        if st.button("👩‍🏫 교사 접속", use_container_width=True):
            st.session_state.page = 'teacher'
            st.rerun()
    with col3:
        st.warning("전체 시스템 및 권한을 관리합니다.")
        if st.button("⚙️ 전체 관리자 접속", use_container_width=True):
            st.session_state.page = 'admin'
            st.rerun()

# ==========================================
# 3. 전체 관리자 페이지 (로그인 & 승인)
# ==========================================
def admin_page():
    st.button("🔙 처음으로 돌아가기", on_click=go_home)
    st.header("⚙️ 전체 관리자 페이지")
    
    # 관리자 로그인 처리
    if not st.session_state.get('admin_logged_in', False):
        st.subheader("관리자 로그인")
        admin_id = st.text_input("아이디")
        admin_pw = st.text_input("비밀번호", type="password")
        if st.button("로그인"):
            if admin_id == "bgkim89" and admin_pw == "gkskrh1165":
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
        return # 로그인 전에는 아래 내용을 렌더링하지 않음

    # 로그인 성공 후 관리자 대시보드
    if st.button("로그아웃", key="admin_logout"):
        st.session_state.admin_logged_in = False
        st.rerun()

    st.divider()
    st.subheader("1. 교사 권한 승인 관리")
    st.write("접속 권한을 신청한 교사 목록입니다. 승인해야 시스템을 사용할 수 있습니다.")
    
    # 미승인 교사 목록 불러오기
    pending_teachers = run_query("SELECT email, name, grade, class_num FROM teachers WHERE is_approved=0")
    if pending_teachers:
        for pt in pending_teachers:
            with st.container(border=True):
                st.write(f"**{pt[1]} 선생님** ({pt[2]}학년 {pt[3]}반) | 이메일: {pt[0]}")
                if st.button("접속 승인", key=f"approve_{pt[0]}"):
                    # 승인 처리 및 교사 설정 초기화 세팅
                    run_query("UPDATE teachers SET is_approved=1 WHERE email=?", (pt[0],), fetch=False)
                    run_query("INSERT OR IGNORE INTO teacher_settings (email, duration, notice) VALUES (?, 20, '')", (pt[0],), fetch=False)
                    st.success(f"{pt[1]} 선생님의 권한이 승인되었습니다.")
                    st.rerun()
    else:
        st.info("승인 대기 중인 교사가 없습니다.")
        
    with st.expander("현재 승인된 교사 목록 보기"):
        approved_teachers = run_query("SELECT email, name, grade, class_num FROM teachers WHERE is_approved=1")
        if approved_teachers:
            df_approved = pd.DataFrame(approved_teachers, columns=["이메일", "성명", "학년", "반"])
            st.dataframe(df_approved)
        else:
            st.write("등록된 교사가 없습니다.")

    st.divider()
    st.subheader("2. 교사 안내 문구 설정")
    admin_notice = st.text_area("교사들이 시스템 접속 시 볼 수 있는 공지사항을 작성해주세요.")
    if st.button("안내 문구 저장"):
        run_query("DELETE FROM admin_settings", fetch=False)
        run_query("INSERT INTO admin_settings (id, notice) VALUES (1, ?)", (admin_notice,), fetch=False)
        st.success("저장되었습니다.")

# ==========================================
# 4. 교사 페이지 (권한 신청 및 데이터 독립)
# ==========================================
def teacher_page():
    st.button("🔙 처음으로 돌아가기", on_click=go_home)
    st.header("👩‍🏫 교사 페이지")
    
    admin_settings = run_query("SELECT notice FROM admin_settings WHERE id=1")
    if admin_settings and admin_settings[0][0]:
        st.info(f"**[관리자 안내사항]**\n{admin_settings[0][0]}")

    # 세션에 교사 이메일이 없는 경우 (로그인/신청 화면)
    if 't_email' not in st.session_state:
        st.subheader("교사 로그인 및 권한 신청")
        email_input = st.text_input("구글 계정 이메일을 입력하세요")
        
        if st.button("확인 및 진행"):
            if not email_input:
                st.error("이메일을 입력해주세요.")
                return
            
            teacher = run_query("SELECT * FROM teachers WHERE email=?", (email_input,))
            if teacher:
                # DB에 정보가 있음
                if teacher[0][4] == 1: # is_approved == 1
                    st.session_state.t_email = email_input
                    st.rerun()
                else:
                    st.warning("전체 관리자의 승인을 대기 중입니다. 승인 후 이용 가능합니다.")
            else:
                # DB에 정보가 없음 -> 신청 폼 보여주기 위해 세션에 임시 저장
                st.session_state.register_email = email_input
                st.rerun()

        # 회원가입(권한 신청) 폼 노출
        if 'register_email' in st.session_state:
            st.divider()
            st.subheader(f"[{st.session_state.register_email}] 권한 신청")
            st.write("처음 접속하셨습니다. 권한 신청을 위해 아래 정보를 입력해주세요.")
            reg_name = st.text_input("성명")
            reg_grade = st.text_input("담당 학년 (예: 1)")
            reg_class = st.text_input("담당 반 (예: 3)")
            
            if st.button("권한 신청하기"):
                if reg_name and reg_grade and reg_class:
                    run_query("INSERT INTO teachers (email, name, grade, class_num, is_approved) VALUES (?, ?, ?, ?, 0)", 
                              (st.session_state.register_email, reg_name, reg_grade, reg_class), fetch=False)
                    st.success("권한 신청이 완료되었습니다. 관리자 승인 후 동일한 이메일로 접속 가능합니다.")
                    del st.session_state['register_email']
                else:
                    st.error("모든 정보를 입력해주세요.")
        return # 로그인 전이므로 아래 대시보드는 숨김

    # ----------------------------------------------------
    # 여기서부터는 교사 인증이 완료된 대시보드 화면
    # ----------------------------------------------------
    email = st.session_state.t_email
    teacher_info = run_query("SELECT * FROM teachers WHERE email=?", (email,))
    t_name, t_grade, t_class = teacher_info[0][1], teacher_info[0][2], teacher_info[0][3]
    
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.success(f"{t_name} 선생님, 환영합니다! ({t_grade}학년 {t_class}반 전용 관리 화면)")
    with col2:
        if st.button("로그아웃"):
            del st.session_state['t_email']
            st.rerun()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["기본 설정", "상담 가능 시간", "학생 명단 관리", "예약 내역 조회", "데이터 다운로드"])

    # (이전과 동일한 탭 내용 유지)
    with tab1:
        st.subheader("상담 설정")
        current_settings = run_query("SELECT duration, notice FROM teacher_settings WHERE email=?", (email,))
        curr_duration = current_settings[0][0] if current_settings else 20
        curr_notice = current_settings[0][1] if current_settings else ""

        duration = st.radio("1회 상담 시간 단위", [20, 30], index=0 if curr_duration == 20 else 1)
        notice = st.text_area("학부모 예약 완료 화면에 노출할 안내 문구", value=curr_notice)
        
        if st.button("설정 저장"):
            run_query("UPDATE teacher_settings SET duration=?, notice=? WHERE email=?", (duration, notice, email), fetch=False)
            st.success("설정이 저장되었습니다.")

    with tab2:
        st.subheader("상담 가능 시간 등록 (10분 단위)")
        avail_date = st.date_input("가능한 연도/월/일 선택")
        colA, colB = st.columns(2)
        time_options = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(8, 22) for m in (0, 10, 20, 30, 40, 50)]
        with colA:
            start_time = st.selectbox("시작 시간", time_options)
        with colB:
            end_time = st.selectbox("종료 시간", time_options, index=12)

        if st.button("가능 시간 추가"):
            run_query("INSERT INTO availability (teacher_email, avail_date, start_time, end_time) VALUES (?, ?, ?, ?)",
                      (email, str(avail_date), start_time, end_time), fetch=False)
            st.success("추가되었습니다.")
            
        avails = run_query("SELECT id, avail_date, start_time, end_time FROM availability WHERE teacher_email=? ORDER BY avail_date, start_time", (email,))
        if avails:
            df_avails = pd.DataFrame(avails, columns=["ID", "일자", "시작시간", "종료시간"])
            st.dataframe(df_avails)
            del_avail_id = st.text_input("삭제할 시간 ID 입력")
            if st.button("해당 시간 삭제"):
                run_query("DELETE FROM availability WHERE id=?", (del_avail_id,), fetch=False)
                st.rerun()

    with tab3:
        st.subheader("학생 데이터 관리")
        df_template = pd.DataFrame(columns=["학년", "반", "번호", "이름", "학번", "공강시간"])
        towrite = io.BytesIO()
        df_template.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button("엑셀 양식 다운로드", towrite, "student_template.xlsx", 
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        uploaded_file = st.file_uploader("학생 정보 엑셀 파일 업로드", type=["xlsx"])
        if uploaded_file is not None:
            df_students = pd.read_excel(uploaded_file)
            if st.button("학생 데이터 DB 저장 (기존 데이터 덮어쓰기)"):
                run_query("DELETE FROM students WHERE teacher_email=?", (email,), fetch=False) 
                for _, row in df_students.iterrows():
                    run_query("INSERT INTO students (teacher_email, grade, class_num, student_num, name, stu_id, free_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (email, str(row['학년']), str(row['반']), str(row['번호']), str(row['이름']), str(row['학번']), str(row['공강시간'])), fetch=False)
                st.success("학생 데이터 업로드 완료")
                
        current_students = run_query("SELECT grade, class_num, student_num, name, stu_id, free_time FROM students WHERE teacher_email=? ORDER BY CAST(student_num AS INTEGER)", (email,))
        if current_students:
            st.dataframe(pd.DataFrame(current_students, columns=["학년", "반", "번호", "이름", "학번", "공강시간"]))

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
            
            del_id = st.text_input("삭제할 예약 ID 입력 (학부모 취소 처리 등)")
            if st.button("예약 내역 삭제"):
                run_query("DELETE FROM bookings WHERE id=?", (del_id,), fetch=False)
                st.success("삭제되었습니다.")
                st.rerun()
        else:
            st.write("접수된 예약이 없습니다.")

    with tab5:
        st.subheader("예약 내역 엑셀 다운로드")
        if bookings:
            export_data = []
            for b in bookings:
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
# 5. 학부모 (예약자) 페이지 - 세션 보안 유지
# ==========================================
def parent_page():
    st.button("🔙 처음으로 돌아가기", on_click=go_home)
    st.header("👩‍👧 학부모 상담 예약")
    
    if 'verified_student' not in st.session_state:
        st.session_state.verified_student = None

    stu_name = st.text_input("자녀 이름")
    stu_id = st.text_input("고유 학번 (예: 10101)")
    
    if st.button("학생 인증 및 정보 조회"):
        student = run_query("SELECT teacher_email, free_time FROM students WHERE name=? AND stu_id=?", (stu_name, stu_id))
        if student:
            st.session_state.verified_student = {
                'name': stu_name, 'stu_id': stu_id,
                'teacher_email': student[0][0], 'free_time': student[0][1]
            }
            st.success("학생 인증이 완료되었습니다.")
        else:
            st.error("일치하는 학생 정보가 없습니다. 이름과 학번을 정확히 확인해주세요.")
            st.session_state.verified_student = None

    if st.session_state.verified_student:
        v_student = st.session_state.verified_student
        t_email = v_student['teacher_email']
        
        if stu_name != v_student['name'] or stu_id != v_student['stu_id']:
             st.warning("입력 정보가 변경되었습니다. 다시 인증해주세요.")
             st.session_state.verified_student = None
             st.stop()
        
        st.divider()
        st.info(f"**[학생 공강 시간]** {v_student['free_time']}")
        
        settings = run_query("SELECT duration, notice FROM teacher_settings WHERE email=?", (t_email,))
        duration_mins = settings[0][0] if settings else 20
        teacher_notice = settings[0][1] if settings else ""
        
        st.subheader(f"상담 날짜 및 시간 선택 ({duration_mins}분 단위)")
        selected_date = st.date_input("상담 희망일 선택")
        
        avails = run_query("SELECT start_time, end_time FROM availability WHERE teacher_email=? AND avail_date=?", 
                           (t_email, str(selected_date)))
        
        if not avails:
            st.warning("선택하신 날짜에 당일 담당 선생님의 상담 일정이 없습니다.")
            return
            
        booked = run_query("SELECT start_time, end_time FROM bookings WHERE teacher_email=? AND book_date=?", 
                           (t_email, str(selected_date)))
        booked_times = [f"{b[0]} ~ {b[1]}" for b in booked]

        all_blocks = []
        for avail in avails:
            blocks = generate_time_blocks(avail[0], avail[1], duration_mins)
            all_blocks.extend(blocks)
            
        available_blocks = [b for b in all_blocks if b not in booked_times]

        if not available_blocks:
            st.warning("선택하신 날짜의 모든 상담 예약이 마감되었습니다.")
            return
            
        selected_block = st.selectbox("상담 희망 시간 선택 (학생의 공강시간을 참고하세요)", available_blocks)
        
        st.divider()
        parent_name = st.text_input("학부모 성명")
        parent_phone = st.text_input("학부모 휴대폰 번호")
        
        if st.button("예약 확정하기"):
            if not parent_name or not parent_phone:
                st.error("성명과 연락처를 모두 입력해주세요.")
                return
                
            start_t, end_t = selected_block.split(" ~ ")
            run_query("INSERT INTO bookings (teacher_email, stu_id, parent_name, phone, book_date, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (t_email, v_student['stu_id'], parent_name, parent_phone, str(selected_date), start_t, end_t), fetch=False)
            
            st.success("예약이 성공적으로 확정되었습니다!")
            if teacher_notice:
                st.info(f"**[선생님 안내사항]**\n{teacher_notice}")
            
            st.session_state.verified_student = None

# ==========================================
# 앱 메인 실행부
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="고등학교 학부모 상담 예약", layout="wide", initial_sidebar_state="collapsed")
    init_db()
    
    # 페이지 라우팅 로직
    if 'page' not in st.session_state:
        st.session_state.page = 'home'
        
    if st.session_state.page == 'home':
        home_page()
    elif st.session_state.page == 'admin':
        admin_page()
    elif st.session_state.page == 'teacher':
        teacher_page()
    elif st.session_state.page == 'parent':
        parent_page()
