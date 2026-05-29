"""
scripts/seed_db.py — Temple Gate Polytechnic Aba
=================================================
Fixed: Course codes are now unique per department by prefixing with dept code
       where shared codes like MTH101, GST101, ECO101 appear in multiple depts.
"""

import sys, os, random
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import create_app, db
from app.models.user import User, Student, Lecturer
from app.models.course import Department, Course
from app.models.result import (AcademicSession, Result, ResultDetail,
                                GPARecord, CGPARecord, CarryoverRecord)
from app.services.grading import compute_grade
from app.services.gpa_engine import recompute_all_for_student
from app.services.carryover_service import process_carryovers_for_session

env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)
random.seed(42)

# ── Nigerian Names ────────────────────────────────────────────────────────────
NAMES = [
    ("Chukwuemeka","Okafor"), ("Adaeze","Nwankwo"), ("Babatunde","Adeyemi"),
    ("Ngozi","Bello"),        ("Ibrahim","Eze"),     ("Fatima","Ibrahim"),
    ("Chinedu","Obi"),        ("Amaka","Abubakar"),  ("Yusuf","Uchenna"),
    ("Blessing","Olawale"),   ("Obinna","Nwosu"),    ("Chisom","Adeleke"),
    ("Abdullahi","Chukwu"),   ("Ifeoma","Mohammed"), ("Tunde","Ogundele"),
    ("Chiamaka","Ezenwachi"), ("Emeka","Suleiman"),  ("Aisha","Okonkwo"),
    ("Kelechi","Adesanya"),   ("Taiwo","Usman"),     ("Oluwaseun","Anyanwu"),
    ("Chinwe","Fadele"),      ("Musa","Oguike"),     ("Chidinma","Lawal"),
    ("Rotimi","Obiora"),      ("Nneka","Danladi"),   ("Usman","Nwachukwu"),
    ("Ebele","Jimoh"),        ("Segun","Onyekachi"), ("Amina","Afolabi"),
    ("Nnamdi","Okeke"),       ("Adaobi","Yusuf"),    ("Garba","Agbara"),
    ("Uchechi","Salisu"),     ("Femi","Ogbueli"),    ("Ogochukwu","Haruna"),
    ("Lawal","Uzoma"),        ("Adaora","Adeloye"),  ("Biodun","Ihejirika"),
    ("Hauwa","Garba"),        ("Ifeanyi","Oyelaran"),("Obiageli","Nwofor"),
    ("Sani","Musa"),          ("Chinyere","Chinonso"),("Dele","Adegoke"),
    ("Onyinye","Oguike"),     ("Kabiru","Jimoh"),    ("Nkechi","Ogundele"),
    ("Tobi","Abubakar"),      ("Zainab","Suleiman"), ("Stella","Onuoha"),
    ("David","Ekwueme"),      ("Grace","Onyia"),     ("Samuel","Agwu"),
    ("Precious","Okoro"),     ("Michael","Ogbuagu"), ("Esther","Nwoke"),
    ("Joseph","Akueme"),      ("Mary","Nwobi"),      ("Daniel","Ugwu"),
    ("Ruth","Ezeoba"),        ("Emmanuel","Nnaji"),  ("Patience","Obiechina"),
    ("Victor","Okwuosa"),     ("Peace","Achebe"),    ("Benjamin","Nweze"),
    ("Miracle","Egwuatu"),    ("Joshua","Onwudiwe"), ("Faith","Okoye"),
    ("Moses","Ndubuisi"),     ("Joy","Ozoemena"),    ("Elijah","Onyemelukwe"),
    ("Comfort","Nzekwe"),     ("Caleb","Okeke"),     ("Goodness","Agbo"),
    ("Gideon","Onah"),        ("Charity","Eze"),     ("Solomon","Iloabachie"),
    ("Gloria","Nwofor"),      ("Philip","Nwogu"),    ("Mercy","Ezenwachi"),
    ("Stephen","Nwobia"),     ("Sarah","Eze"),       ("Andrew","Agbo"),
    ("Rebecca","Nzotta"),     ("Peter","Ugwunna"),   ("Deborah","Ifeanyi"),
    ("Paul","Ezedike"),       ("Lydia","Nwachukwu"), ("Matthew","Obi"),
    ("Naomi","Ogbu"),         ("Mark","Ekwueme"),    ("Tabitha","Onuoha"),
    ("Luke","Onyia"),         ("Dorcas","Agwu"),     ("John","Okoro"),
    ("Priscilla","Ogbuagu"),  ("James","Nwoke"),     ("Abigail","Akueme"),
    ("Thomas","Nwobi"),       ("Rachel","Ezeoba"),   ("Simon","Nnaji"),
]

name_pool = list(NAMES)
random.shuffle(name_pool)
name_idx = 0

def next_name():
    global name_idx
    pair = name_pool[name_idx % len(name_pool)]
    name_idx += 1
    return pair

def make_user(email, password, role, first, last):
    u = User(email=email.lower(), role=role,
             first_name=first, last_name=last, is_active=True)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    return u

def gen_score(scale, tier="mixed"):
    r = random.random()
    if scale == "5.0":
        if tier == "high":   return random.randint(70,95) if r<0.6 else random.randint(55,69)
        elif tier == "low":  return random.randint(25,44) if r<0.5 else random.randint(45,55)
        else:
            if r<0.12:   return random.randint(70,95)
            elif r<0.70: return random.randint(50,69)
            else:        return random.randint(25,49)
    else:  # 4.0
        if tier == "high":   return random.randint(75,95) if r<0.6 else random.randint(60,74)
        elif tier == "low":  return random.randint(28,44) if r<0.5 else random.randint(45,55)
        else:
            if r<0.12:   return random.randint(75,95)
            elif r<0.70: return random.randint(50,74)
            else:        return random.randint(28,49)

def add_result(student, course, session, status, lec_user, scale, tier="mixed"):
    existing = Result.query.filter_by(
        student_id=student.id,
        course_id=course.id,
        session_id=session.id
    ).first()
    if existing:
        return existing

    score = gen_score(scale, tier)
    grade, gp = compute_grade(score, scale)
    ca   = round(score * 0.30, 1)
    exam = round(score * 0.70, 1)

    r = Result(
        student_id=student.id, course_id=course.id,
        session_id=session.id, submitted_by=lec_user.id,
        score=score, grade=grade, grade_point=gp, status=status,
    )
    if status == "approved":
        r.approved_at = datetime.utcnow()
    db.session.add(r)
    db.session.flush()
    db.session.add(ResultDetail(
        result_id=r.id, ca_score=ca, ca_max=30.0,
        practical_score=None, practical_max=0.0,
        exam_score=exam, exam_max=70.0,
    ))
    return r

# ── Department / Course definitions ──────────────────────────────────────────
# IMPORTANT: All course codes are UNIQUE across the whole system.
# Shared subjects (Maths, English) get dept-prefixed codes to avoid collision.
# e.g. BAM uses BAM-MTH101, CSC uses CSC-MTH101 — different rows, same subject.

DEPT_DATA = {
    "BAM": {
        "name": "Business Administration and Management",
        "scale": "4.0",
        "courses": [
            # (unique_code, display_title, units, level, semester)
            ("BAM101","Principles of Management",       3,100,1),
            ("BAM102","Business Communication",         2,100,1),
            ("BAM-ECO101","Introduction to Economics",  3,100,1),
            ("BAM-GST101","Use of English I",           2,100,1),
            ("BAM-MTH101","Business Mathematics",       2,100,1),
            ("BAM103","Organisational Behaviour",       3,100,2),
            ("BAM104","Introduction to Marketing",      2,100,2),
            ("BAM-ACC101","Financial Accounting I",     3,100,2),
            ("BAM-GST102","Communication Skills",       2,100,2),
            ("BAM201","Human Resource Management",      3,200,1),
            ("BAM202","Business Law",                   2,200,1),
            ("BAM203","Entrepreneurship Development",   3,200,1),
            ("BAM-ECO201","Microeconomics",             2,200,1),
            ("BAM204","Financial Management",           3,200,2),
            ("BAM205","Strategic Management",           3,200,2),
            ("BAM206","Business Research Methods",      2,200,2),
        ],
        "lecturers": [
            {"level":100,"sem":1,"codes":["BAM101","BAM102","BAM-ECO101"]},
            {"level":100,"sem":1,"codes":["BAM-GST101","BAM-MTH101"]},
            {"level":100,"sem":2,"codes":["BAM103","BAM104","BAM-ACC101"]},
            {"level":100,"sem":2,"codes":["BAM-GST102"]},
            {"level":200,"sem":1,"codes":["BAM201","BAM202","BAM203"]},
            {"level":200,"sem":1,"codes":["BAM-ECO201"]},
            {"level":200,"sem":2,"codes":["BAM204","BAM205","BAM206"]},
        ],
    },
    "CSC": {
        "name": "Computer Science",
        "scale": "5.0",
        "courses": [
            ("CSC101","Introduction to Programming",    3,100,1),
            ("CSC102","Computer Fundamentals",          2,100,1),
            ("CSC-MTH101","Elementary Mathematics",     3,100,1),
            ("CSC-GST101","Use of English I",           2,100,1),
            ("CSC-PHY101","Physics for Computing",      2,100,1),
            ("CSC103","Data Structures",                3,100,2),
            ("CSC104","Digital Logic Design",           2,100,2),
            ("CSC-MTH102","Discrete Mathematics",       3,100,2),
            ("CSC-GST102","Communication Skills",       2,100,2),
            ("CSC201","Object-Oriented Programming",    3,200,1),
            ("CSC202","Database Management Systems",    3,200,1),
            ("CSC203","Computer Networks",              2,200,1),
            ("CSC-MTH201","Numerical Methods",          2,200,1),
            ("CSC204","Operating Systems",              3,200,2),
            ("CSC205","Software Engineering",           3,200,2),
            ("CSC206","Web Technologies",               2,200,2),
        ],
        "lecturers": [
            {"level":100,"sem":1,"codes":["CSC101","CSC102","CSC-MTH101"]},
            {"level":100,"sem":1,"codes":["CSC-GST101","CSC-PHY101"]},
            {"level":100,"sem":2,"codes":["CSC103","CSC104","CSC-MTH102"]},
            {"level":100,"sem":2,"codes":["CSC-GST102"]},
            {"level":200,"sem":1,"codes":["CSC201","CSC202","CSC203"]},
            {"level":200,"sem":1,"codes":["CSC-MTH201"]},
            {"level":200,"sem":2,"codes":["CSC204","CSC205","CSC206"]},
        ],
    },
    "STA": {
        "name": "Statistics",
        "scale": "4.0",
        "courses": [
            ("STA101","Introduction to Statistics",     3,100,1),
            ("STA-MTH101","Elementary Mathematics",     3,100,1),
            ("STA102","Probability Theory",             2,100,1),
            ("STA-GST101","Use of English I",           2,100,1),
            ("STA-ECO101","Introduction to Economics",  2,100,1),
            ("STA103","Statistical Methods",            3,100,2),
            ("STA104","Data Collection Methods",        2,100,2),
            ("STA-MTH102","Calculus",                   3,100,2),
            ("STA-GST102","Communication Skills",       2,100,2),
            ("STA201","Regression Analysis",            3,200,1),
            ("STA202","Sampling Theory",                3,200,1),
            ("STA203","Statistical Computing",          2,200,1),
            ("STA-MTH201","Linear Algebra",             2,200,1),
            ("STA204","Time Series Analysis",           3,200,2),
            ("STA205","Experimental Design",            3,200,2),
            ("STA206","Biostatistics",                  2,200,2),
        ],
        "lecturers": [
            {"level":100,"sem":1,"codes":["STA101","STA-MTH101","STA102"]},
            {"level":100,"sem":1,"codes":["STA-GST101","STA-ECO101"]},
            {"level":100,"sem":2,"codes":["STA103","STA104","STA-MTH102"]},
            {"level":100,"sem":2,"codes":["STA-GST102"]},
            {"level":200,"sem":1,"codes":["STA201","STA202","STA203"]},
            {"level":200,"sem":1,"codes":["STA-MTH201"]},
            {"level":200,"sem":2,"codes":["STA204","STA205","STA206"]},
        ],
    },
    "ACC": {
        "name": "Accountancy",
        "scale": "4.0",
        "courses": [
            ("ACC101","Financial Accounting I",         3,100,1),
            ("ACC102","Cost Accounting",                2,100,1),
            ("ACC-ECO101","Introduction to Economics",  3,100,1),
            ("ACC-GST101","Use of English I",           2,100,1),
            ("ACC-MTH101","Business Mathematics",       2,100,1),
            ("ACC103","Management Accounting",          3,100,2),
            ("ACC104","Business Law",                   2,100,2),
            ("ACC105","Auditing Principles",            3,100,2),
            ("ACC-GST102","Communication Skills",       2,100,2),
            ("ACC201","Intermediate Accounting",        3,200,1),
            ("ACC202","Taxation",                       3,200,1),
            ("ACC203","Public Sector Accounting",       2,200,1),
            ("ACC-ECO201","Macroeconomics",             2,200,1),
            ("ACC204","Advanced Financial Accounting",  3,200,2),
            ("ACC205","Financial Reporting",            3,200,2),
            ("ACC206","Accounting Research Methods",    2,200,2),
        ],
        "lecturers": [
            {"level":100,"sem":1,"codes":["ACC101","ACC102","ACC-ECO101"]},
            {"level":100,"sem":1,"codes":["ACC-GST101","ACC-MTH101"]},
            {"level":100,"sem":2,"codes":["ACC103","ACC104","ACC105"]},
            {"level":100,"sem":2,"codes":["ACC-GST102"]},
            {"level":200,"sem":1,"codes":["ACC201","ACC202","ACC203"]},
            {"level":200,"sem":1,"codes":["ACC-ECO201"]},
            {"level":200,"sem":2,"codes":["ACC204","ACC205","ACC206"]},
        ],
    },
    "LAW": {
        "name": "Law",
        "scale": "5.0",
        "courses": [
            ("LAW101","Introduction to Law",            3,100,1),
            ("LAW102","Constitutional Law",             3,100,1),
            ("LAW103","Legal Methods",                  2,100,1),
            ("LAW-GST101","Use of English I",           2,100,1),
            ("LAW-GOV101","Government and Politics",    2,100,1),
            ("LAW104","Contract Law",                   3,100,2),
            ("LAW105","Criminal Law",                   3,100,2),
            ("LAW106","Law of Tort",                    2,100,2),
            ("LAW-GST102","Communication Skills",       2,100,2),
            ("LAW201","Property Law",                   3,200,1),
            ("LAW202","Administrative Law",             3,200,1),
            ("LAW203","Commercial Law",                 2,200,1),
            ("LAW-GOV201","International Law",          2,200,1),
            ("LAW204","Equity and Trust",               3,200,2),
            ("LAW205","Family Law",                     3,200,2),
            ("LAW206","Legal Research Methods",         2,200,2),
        ],
        "lecturers": [
            {"level":100,"sem":1,"codes":["LAW101","LAW102","LAW103"]},
            {"level":100,"sem":1,"codes":["LAW-GST101","LAW-GOV101"]},
            {"level":100,"sem":2,"codes":["LAW104","LAW105","LAW106"]},
            {"level":100,"sem":2,"codes":["LAW-GST102"]},
            {"level":200,"sem":1,"codes":["LAW201","LAW202","LAW203"]},
            {"level":200,"sem":1,"codes":["LAW-GOV201"]},
            {"level":200,"sem":2,"codes":["LAW204","LAW205","LAW206"]},
        ],
    },
}

HOD_NAMES = {
    "BAM": ("Ngozi",        "Okafor"),
    "CSC": ("Chukwuemeka",  "Eze"),
    "STA": ("Ibrahim",      "Bello"),
    "ACC": ("Fatima",       "Adeyemi"),
    "LAW": ("Babatunde",    "Nwankwo"),
}

def seed():
    with app.app_context():
        print("\n" + "="*65)
        print("  Temple Gate Polytechnic Aba — Full Database Seeder")
        print("="*65)

        db.drop_all()
        db.create_all()
        print("\n[1] Database wiped and recreated.")

        # Admin
        make_user("admin@tgpa.edu.ng","TGPAAdmin@2024","admin","System","Administrator")
        db.session.commit()
        print("[2] Admin created.")

        dept_objs   = {}
        course_objs = {}  # dept_code -> {course_code -> Course obj}
        lec_objs    = {}  # dept_code -> list of dicts
        hod_users   = {}

        for dept_code, dinfo in DEPT_DATA.items():
            # Department
            dept = Department(name=dinfo["name"], code=dept_code,
                              grading_scale=dinfo["scale"])
            db.session.add(dept)
            db.session.flush()
            dept_objs[dept_code]   = dept
            course_objs[dept_code] = {}

            # Courses — each code is unique because we prefixed shared ones
            for (ccode, ctitle, unit, level, sem) in dinfo["courses"]:
                c = Course(code=ccode, title=ctitle, unit=unit,
                           level=level, semester=sem, department_id=dept.id)
                db.session.add(c)
                db.session.flush()
                course_objs[dept_code][ccode] = c

            # HOD
            fn, ln = HOD_NAMES[dept_code]
            hod_email = f"hod.{dept_code.lower()}@tgpa.edu.ng"
            hod_u = make_user(hod_email, f"{dept_code}Hod@2024", "hod", fn, ln)
            dept.hod_user_id = hod_u.id
            hod_users[dept_code]   = hod_u

            # Lecturers (7 per dept, 2-3 courses each)
            lec_objs[dept_code] = []
            for idx, ldef in enumerate(dinfo["lecturers"], start=1):
                fn2, ln2 = next_name()
                lec_email = f"lec.{dept_code.lower()}.{idx:02d}@tgpa.edu.ng"
                lec_u = make_user(lec_email, f"{dept_code}Lecturer@2024",
                                  "lecturer", fn2, ln2)
                course_list = [
                    course_objs[dept_code][cc]
                    for cc in ldef["codes"]
                    if cc in course_objs[dept_code]
                ]
                lec = Lecturer(
                    user_id=lec_u.id,
                    staff_id=f"TGPA/{dept_code}/LEC/{idx:03d}",
                    department_id=dept.id
                )
                lec.courses = course_list
                db.session.add(lec)
                db.session.flush()
                lec_objs[dept_code].append({
                    "user":  lec_u,
                    "codes": ldef["codes"],
                    "level": ldef["level"],
                    "sem":   ldef["sem"],
                })

        db.session.commit()
        print("[3] Departments, courses, HODs, lecturers created.")

        # Sessions
        SESS_100_1 = AcademicSession(session_name="2024/2025",semester=1,
                                     is_current=True, is_results_released=False)
        SESS_100_2 = AcademicSession(session_name="2023/2024",semester=2,
                                     is_current=False,is_results_released=True)
        SESS_200_1 = AcademicSession(session_name="2023/2024",semester=1,
                                     is_current=False,is_results_released=True)
        SESS_200_2 = AcademicSession(session_name="2022/2023",semester=2,
                                     is_current=False,is_results_released=True)
        for s in [SESS_100_1,SESS_100_2,SESS_200_1,SESS_200_2]:
            db.session.add(s)
        db.session.flush()
        db.session.commit()
        print("[4] Academic sessions created.")

        # Students
        print("[5] Creating students and results...")
        all_students = {}
        creds = []

        for dept_code, dept in dept_objs.items():
            scale = dept.grading_scale
            all_students[dept_code] = {100: [], 200: []}

            for level in [100, 200]:
                entry_year = 2024 if level == 100 else 2023
                for s_num in range(1, 11):
                    fn, ln = next_name()
                    # Matric: TGPA/2024/001/CSC
                    matric = f"TGPA/{entry_year}/{s_num:03d}/{dept_code}"
                    # Email: tgpa.2024.001.csc@tgpa.edu.ng
                    email  = f"tgpa.{entry_year}.{s_num:03d}.{dept_code.lower()}@tgpa.edu.ng"
                    pwd    = f"{dept_code}Student@{entry_year}"

                    u = make_user(email, pwd, "student", fn, ln)
                    student = Student(
                        user_id=u.id, matric_number=matric,
                        level=level, grading_scale=scale,
                        department_id=dept.id,
                    )
                    db.session.add(student)
                    db.session.flush()
                    all_students[dept_code][level].append(student)
                    if s_num == 1:
                        creds.append((dept_code,level,matric,email,pwd))

        db.session.commit()
        print("    Students created (10 per level × 2 levels × 5 depts = 100)")

        def get_lec_user(dept_code, level, sem, course_code):
            for ldef in lec_objs[dept_code]:
                if ldef["level"]==level and ldef["sem"]==sem and course_code in ldef["codes"]:
                    return ldef["user"]
            return lec_objs[dept_code][0]["user"]

        for dept_code, dept in dept_objs.items():
            scale    = dept.grading_scale
            students = all_students[dept_code]
            courses  = course_objs[dept_code]

            # 200L Sem 1 → APPROVED
            for student in students[200]:
                tier = "high" if student.id%3==0 else ("low" if student.id%5==0 else "mixed")
                for c in [x for x in courses.values() if x.level==200 and x.semester==1]:
                    add_result(student, c, SESS_200_1, "approved",
                               get_lec_user(dept_code,200,1,c.code), scale, tier)

            # 200L Sem 2 → APPROVED
            for student in students[200]:
                tier = "high" if student.id%3==0 else ("low" if student.id%5==0 else "mixed")
                for c in [x for x in courses.values() if x.level==200 and x.semester==2]:
                    add_result(student, c, SESS_200_2, "approved",
                               get_lec_user(dept_code,200,2,c.code), scale, tier)

            # 100L Sem 2 → PENDING (HOD inbox)
            for student in students[100]:
                for c in [x for x in courses.values() if x.level==100 and x.semester==2]:
                    add_result(student, c, SESS_100_2, "pending",
                               get_lec_user(dept_code,100,2,c.code), scale, "mixed")

            # 100L Sem 1 → DRAFT for first 5, empty for last 5
            for student in students[100][:5]:
                for c in [x for x in courses.values() if x.level==100 and x.semester==1]:
                    add_result(student, c, SESS_100_1, "draft",
                               get_lec_user(dept_code,100,1,c.code), scale, "mixed")

            db.session.commit()

        print("    Results created (approved / pending / draft mix)")

        # GPA / CGPA
        print("[6] Computing GPA/CGPA for approved results...")
        for dept_code in dept_objs:
            for student in all_students[dept_code][200]:
                try:
                    recompute_all_for_student(student.id, SESS_200_1.id)
                    recompute_all_for_student(student.id, SESS_200_2.id)
                    process_carryovers_for_session(student.id, SESS_200_1.id)
                    process_carryovers_for_session(student.id, SESS_200_2.id)
                except Exception as e:
                    print(f"    Warning: {e}")
        db.session.commit()
        print("    GPA/CGPA computed.")

        # ── Print credentials ─────────────────────────────────────────
        print("\n" + "="*65)
        print("  SEEDING COMPLETE!")
        print("="*65)

        print("\n── ADMIN ────────────────────────────────────────────────────")
        print("  Email    : admin@tgpa.edu.ng")
        print("  Password : TGPAAdmin@2024")

        print("\n── HOD ACCOUNTS ─────────────────────────────────────────────")
        for code in DEPT_DATA:
            print(f"  hod.{code.lower()}@tgpa.edu.ng   /   {code}Hod@2024")

        print("\n── LECTURER ACCOUNTS ────────────────────────────────────────")
        print("  Pattern : lec.DEPTCODE.NN@tgpa.edu.ng  /  DEPTCODELecturer@2024")
        for code in DEPT_DATA:
            print(f"  {code}: lec.{code.lower()}.01 to lec.{code.lower()}.07  /  {code}Lecturer@2024")

        print("\n── STUDENT ACCOUNTS (first student per dept per level) ───────")
        print(f"  {'Matric':<25} {'Email':<45} Password")
        print(f"  {'-'*100}")
        for (dc,lv,mat,em,pw) in creds:
            print(f"  {mat:<25} {em:<45} {pw}")

        print("\n── STUDENT LOGIN PATTERN ────────────────────────────────────")
        print("  Email    : tgpa.YEAR.SERIAL.deptcode@tgpa.edu.ng")
        print("  Password : DEPTCODEStudent@YEAR")
        print("  100L (year 2024) serial 001-010 → CSCStudent@2024")
        print("  200L (year 2023) serial 001-010 → CSCStudent@2023")

        print("\n── WHAT EACH ROLE SEES ──────────────────────────────────────")
        print("  Student 200L → CGPA, full results, AI prediction, transcript")
        print("  Student 100L → Sem2 pending message; Sem1 draft visible")
        print("  Lecturer     → Dashboard: 5 drafts + 5 empty (enter scores)")
        print("  HOD          → Pending approvals: 100L Sem2 all 5 depts")
        print("  Admin        → 100 students, 35 lecturers, 5 HODs, 80 courses")
        print(f"\n  Open: http://localhost:5000\n")

if __name__ == "__main__":
    seed()
