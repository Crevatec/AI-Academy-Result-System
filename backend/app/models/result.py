"""
backend/app/models/result.py  (UPDATED)
----------------------------------------
New additions:
- ResultDetail: stores CA, practical, and exam scores per result
- ResultAccessControl: HOD can restrict a student's result access
- CarryoverRecord: tracks failed courses and recommended retake session
"""

from app import db


class AcademicSession(db.Model):
    __tablename__ = "academic_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(20), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    is_current = db.Column(db.Boolean, default=False)
    is_results_released = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint("session_name", "semester", name="uq_session_semester"),
    )

    results = db.relationship("Result", back_populates="academic_session")

    def __repr__(self):
        return f"<AcademicSession {self.session_name} Sem {self.semester}>"


class Result(db.Model):
    """
    One student's result for one course in one semester.
    The total `score` is computed from CA + Practical + Exam (stored in ResultDetail).

    Statuses: draft → pending → approved | rejected
    """
    __tablename__ = "results"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("academic_sessions.id"), nullable=False)
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    score = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(2), nullable=False)
    grade_point = db.Column(db.Float, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="draft")
    hod_comment = db.Column(db.Text, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "session_id", name="uq_result"),
    )

    student = db.relationship("Student", back_populates="results")
    course = db.relationship("Course", back_populates="results")
    academic_session = db.relationship("AcademicSession", back_populates="results")
    detail = db.relationship("ResultDetail", back_populates="result",
                             uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Result Student:{self.student_id} Course:{self.course_id} [{self.status}]>"


class ResultDetail(db.Model):
    """
    Assessment breakdown for a result.
    Total = ca_score + practical_score + exam_score.
    Lecturers enter each component; system validates total <= 100.
    """
    __tablename__ = "result_details"

    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey("results.id"),
                          unique=True, nullable=False)

    ca_score = db.Column(db.Float, nullable=True)
    ca_max = db.Column(db.Float, default=30.0)

    practical_score = db.Column(db.Float, nullable=True)
    practical_max = db.Column(db.Float, default=0.0)

    exam_score = db.Column(db.Float, nullable=True)
    exam_max = db.Column(db.Float, default=70.0)

    result = db.relationship("Result", back_populates="detail")

    @property
    def computed_total(self) -> float:
        return (
            (self.ca_score or 0)
            + (self.practical_score or 0)
            + (self.exam_score or 0)
        )

    def __repr__(self):
        return (f"<ResultDetail result:{self.result_id} "
                f"CA:{self.ca_score} Prac:{self.practical_score} Exam:{self.exam_score}>")


class ResultAccessControl(db.Model):
    """
    Per-student result access gate controlled by HOD.
    Default: access_granted = True.
    When False, student sees a blocked message with restriction_reason.
    """
    __tablename__ = "result_access_controls"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"),
                           unique=True, nullable=False)
    access_granted = db.Column(db.Boolean, default=True, nullable=False)
    restriction_reason = db.Column(db.String(255), nullable=True)
    restricted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    restricted_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student", backref=db.backref("access_control", uselist=False))

    def __repr__(self):
        status = "GRANTED" if self.access_granted else "BLOCKED"
        return f"<ResultAccess Student:{self.student_id} [{status}]>"


class CarryoverRecord(db.Model):
    """
    Tracks a student's failed course as a carryover.

    Auto-created when HOD approves a result with grade = 'F'.
    System recommends retake semester based on this rule:
        Failed Level X Sem Y → Retake Level X+100 Sem Y
    e.g. Failed 100L Sem1 → Retake 200L Sem1

    Status: pending | cleared | deferred
    """
    __tablename__ = "carryover_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    failed_session_id = db.Column(db.Integer, db.ForeignKey("academic_sessions.id"), nullable=False)
    failed_score = db.Column(db.Float, nullable=False)

    recommended_retake_level = db.Column(db.Integer, nullable=True)
    recommended_retake_semester = db.Column(db.Integer, nullable=True)
    recommended_retake_session = db.Column(db.String(20), nullable=True)

    status = db.Column(db.String(20), default="pending", nullable=False)
    cleared_session_id = db.Column(db.Integer, db.ForeignKey("academic_sessions.id"), nullable=True)
    cleared_score = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "failed_session_id", name="uq_carryover"),
    )

    student = db.relationship("Student", backref=db.backref("carryovers", lazy="dynamic"))
    course = db.relationship("Course")
    failed_session = db.relationship("AcademicSession", foreign_keys=[failed_session_id])

    def __repr__(self):
        return f"<Carryover Student:{self.student_id} Course:{self.course_id} [{self.status}]>"


class GPARecord(db.Model):
    __tablename__ = "gpa_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("academic_sessions.id"), nullable=False)

    gpa = db.Column(db.Float, nullable=False)
    total_units = db.Column(db.Integer, nullable=False)
    total_points = db.Column(db.Float, nullable=False)
    classification = db.Column(db.String(50), nullable=True)
    computed_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("student_id", "session_id", name="uq_gpa_per_session"),
    )

    student = db.relationship("Student", back_populates="gpa_records")
    session = db.relationship("AcademicSession")

    def __repr__(self):
        return f"<GPARecord Student:{self.student_id} GPA:{self.gpa}>"


class CGPARecord(db.Model):
    __tablename__ = "cgpa_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), unique=True, nullable=False)

    cgpa = db.Column(db.Float, nullable=False)
    total_units_cumulative = db.Column(db.Integer, nullable=False)
    total_points_cumulative = db.Column(db.Float, nullable=False)
    classification = db.Column(db.String(50), nullable=True)
    semesters_completed = db.Column(db.Integer, default=0)

    last_updated = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<CGPARecord Student:{self.student_id} CGPA:{self.cgpa}>"
class PredictionRecord(db.Model):
    """
    Stores AI prediction outputs per student per session.
    Referenced in Chapter 3, Section 3.6 (Predictions Table).

    Created/updated automatically when:
    - HOD approves results (GPA computed → AI runs → prediction saved)
    - Student visits dashboard (prediction refreshed)

    Keeps a history of predictions so administrators can track
    whether a student's risk level improved or worsened over time.
    """
    __tablename__ = "prediction_records"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False
    )
    session_id = db.Column(
        db.Integer, db.ForeignKey("academic_sessions.id"), nullable=True
    )

    # Output from Random Forest classifier
    risk_level = db.Column(db.String(20), nullable=False)
    # e.g. "Excellent", "Average", "At Risk"

    # Output from Linear Regression
    predicted_gpa = db.Column(db.Float, nullable=True)

    # Confidence score from classifier (0.0 – 1.0)
    confidence = db.Column(db.Float, nullable=True)

    # Which model was used
    method = db.Column(db.String(60), nullable=True)

    # Classifier metrics at time of prediction
    accuracy  = db.Column(db.Float, nullable=True)
    precision = db.Column(db.Float, nullable=True)
    recall    = db.Column(db.Float, nullable=True)
    f1_score  = db.Column(db.Float, nullable=True)

    # Regressor metric
    mse = db.Column(db.Float, nullable=True)

    generated_at = db.Column(
        db.DateTime, server_default=db.func.now()
    )

    student = db.relationship(
        "Student",
        backref=db.backref("predictions", lazy="dynamic")
    )

    def __repr__(self):
        return (
            f"<PredictionRecord Student:{self.student_id} "
            f"Risk:{self.risk_level} GPA:{self.predicted_gpa}>"
        )