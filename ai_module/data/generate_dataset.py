"""
ai_module/data/generate_dataset.py
------------------------------------
Generates realistic synthetic student result data for training the AI model.
This is the dataset script from the original project brief — kept intact
and placed in the correct folder.

Run from project root:
    python ai_module/data/generate_dataset.py

Output:
    ai_module/data/students.csv
    ai_module/data/results.csv

Then train the model:
    python backend/app/ai/train.py
"""

import os
import random
import pandas as pd

# ── Grading Systems ───────────────────────────────────────────────────────────

UNIVERSITY_5 = {
    "scale": 5.0,
    "grade_map": [
        (70, 100, "A", 5.00), (60, 69, "B", 4.00), (50, 59, "C", 3.00),
        (45, 49, "D", 2.00),  (40, 44, "E", 1.00), (0,  39, "F", 0.00),
    ],
    "classification": [
        (4.50, 5.00, "First Class"),       (3.50, 4.49, "Second Class Upper"),
        (2.40, 3.49, "Second Class Lower"),(1.50, 2.39, "Third Class"),
        (0.00, 1.49, "Probation/Fail"),
    ]
}

POLYTECHNIC_4 = {
    "scale": 4.0,
    "grade_map": [
        (80, 100, "A", 4.00), (70, 79, "B", 3.50), (60, 69, "C", 3.00),
        (50, 59, "D", 2.50),  (40, 49, "E", 2.00), (0,  39, "F", 0.00),
    ],
    "classification": [
        (3.50, 4.00, "Distinction"),  (3.00, 3.49, "Upper Credit"),
        (2.50, 2.99, "Lower Credit"), (2.00, 2.49, "Pass"),
        (0.00, 1.99, "Fail"),
    ]
}

FIRST_NAMES = ["Emeka","Amina","Chinedu","Tolu","Fatima","Ibrahim",
               "Blessing","Uche","David","Ngozi"]
LAST_NAMES  = ["Okafor","Bello","Adebayo","Ibrahim","Eze",
               "Ogunleye","Mohammed","Nwankwo","Okoro","Danladi"]
DEPARTMENTS = ["Computer Science","Accounting","Electrical Engineering",
               "Business Administration","Mass Communication"]
COURSES = [
    ("CSC101","Introduction to Programming",3),
    ("CSC102","Computer Fundamentals",2),
    ("ACC101","Principles of Accounting",3),
    ("MTH101","Elementary Mathematics",3),
    ("GST101","Use of English",2),
    ("ECO101","Microeconomics",2),
    ("BUS101","Introduction to Business",2),
]


def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def get_grade(score, grading_system):
    for min_s, max_s, grade, gp in grading_system["grade_map"]:
        if min_s <= score <= max_s:
            return grade, gp
    return "F", 0.0


def classify_cgpa(cgpa, grading_system):
    for min_c, max_c, label in grading_system["classification"]:
        if min_c <= cgpa <= max_c:
            return label
    return "Unknown"


def generate_score(institution_type):
    r = random.random()
    if institution_type == "University":
        if r < 0.10:   return random.randint(70, 95)
        elif r < 0.70: return random.randint(50, 69)
        else:          return random.randint(30, 49)
    else:
        if r < 0.10:   return random.randint(80, 95)
        elif r < 0.70: return random.randint(55, 79)
        else:          return random.randint(30, 54)


def generate_students(n=200):
    students = []
    for i in range(1, n + 1):
        institution = random.choice(["University", "Polytechnic"])
        scale = 5.0 if institution == "University" else 4.0
        students.append({
            "student_id": f"STU{i:04d}",
            "name": generate_name(),
            "department": random.choice(DEPARTMENTS),
            "institution_type": institution,
            "grading_scale": scale,
            "level": random.choice([100, 200, 300, 400]),
            "session": "2024/2025",
        })
    return students


def generate_results(students):
    results = []
    for student in students:
        grading_system = UNIVERSITY_5 if student["grading_scale"] == 5.0 else POLYTECHNIC_4
        courses = random.sample(COURSES, random.randint(5, 7))
        semester_results = []

        for course_code, title, unit in courses:
            score = generate_score(student["institution_type"])
            grade, gp = get_grade(score, grading_system)
            record = {
                "student_id":    student["student_id"],
                "name":          student["name"],
                "institution_type": student["institution_type"],
                "grading_scale": student["grading_scale"],
                "course_code":   course_code,
                "course_title":  title,
                "course_unit":   unit,
                "score":         score,
                "grade":         grade,
                "grade_point":   gp,
            }
            semester_results.append(record)
            results.append(record)

        total_points = sum(r["grade_point"] * r["course_unit"] for r in semester_results)
        total_units  = sum(r["course_unit"] for r in semester_results)
        student["GPA"] = round(total_points / total_units, 2)

    return results


def compute_cgpa(results, students):
    cgpa_map = {}
    for student in students:
        sid = student["student_id"]
        student_results = [r for r in results if r["student_id"] == sid]
        total_points = sum(r["grade_point"] * r["course_unit"] for r in student_results)
        total_units  = sum(r["course_unit"] for r in student_results)
        cgpa = round(total_points / total_units, 2) if total_units else 0
        grading_system = UNIVERSITY_5 if student["grading_scale"] == 5.0 else POLYTECHNIC_4
        classification = classify_cgpa(cgpa, grading_system)
        cgpa_map[sid] = {"CGPA": cgpa, "classification": classification}
    return cgpa_map


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    students = generate_students(200)
    results  = generate_results(students)
    cgpa_data = compute_cgpa(results, students)

    for r in results:
        r["CGPA"]           = cgpa_data[r["student_id"]]["CGPA"]
        r["classification"] = cgpa_data[r["student_id"]]["classification"]

    df_students = pd.DataFrame(students)
    df_results  = pd.DataFrame(results)

    students_path = os.path.join(out_dir, "students.csv")
    results_path  = os.path.join(out_dir, "results.csv")

    df_students.to_csv(students_path, index=False)
    df_results.to_csv(results_path, index=False)

    print(f"✓ Dataset generated:")
    print(f"  {students_path}")
    print(f"  {results_path}")
    print(f"  {len(df_students)} students, {len(df_results)} result records")


if __name__ == "__main__":
    main()
