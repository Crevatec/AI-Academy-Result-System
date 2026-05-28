"""
backend/app/services/email_service.py
--------------------------------------
Email notification service for AcadResult System.
Sends emails to students when:
  1. Results are released and approved
  2. Student has low CGPA (at risk warning)
  3. HOD is notified when lecturer submits results
  4. Lecturer is notified when HOD rejects results

SETUP FOR GMAIL:
  1. Go to your Google Account → Security
  2. Enable 2-Step Verification
  3. Go to App Passwords → Generate a password for "Mail"
  4. Copy the 16-character password into your .env:
     MAIL_USERNAME=yourgmail@gmail.com
     MAIL_PASSWORD=xxxx xxxx xxxx xxxx

SETUP FOR ANY SMTP:
  MAIL_SERVER=smtp.yourserver.com
  MAIL_PORT=587
  MAIL_USERNAME=your@email.com
  MAIL_PASSWORD=yourpassword
"""

from flask import current_app, render_template_string
from flask_mail import Message
from app import mail


# ── Email Templates ────────────────────────────────────────────────────────────

RESULT_RELEASED_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#f9f9f9;">

  <!-- Header -->
  <div style="background: #1a3c6b; padding: 25px 30px; text-align: center;">
    <h1 style="color: white; margin: 0; font-size: 22px;">🎓 {{ institution_name }}</h1>
    <p style="color: #a8c4e8; margin: 6px 0 0 0; font-size: 14px;">Academic Result Notification</p>
  </div>

  <!-- Body -->
  <div style="padding: 30px; background: white; border: 1px solid #e0e0e0;">
    <p style="font-size: 15px;">Dear <strong>{{ student_name }}</strong>,</p>

    <p style="font-size: 15px; line-height: 1.7;">
      Your academic results for <strong>{{ session_name }} &mdash; Semester {{ semester }}</strong>
      have been approved and are now available on your student portal.
    </p>

    <!-- Result Summary Box -->
    <div style="background: #f0f6ff; border: 1px solid #c5d8f5; border-radius: 8px; padding: 20px; margin: 20px 0;">
      <h3 style="margin: 0 0 15px 0; color: #1a3c6b; font-size: 16px;">📊 Result Summary</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr style="border-bottom: 1px solid #dde;">
          <td style="padding: 10px 5px; color: #555; font-size: 14px;">Semester GPA:</td>
          <td style="padding: 10px 5px; font-weight: bold; color: #1a3c6b; font-size: 18px;">{{ gpa }} / {{ scale }}</td>
        </tr>
        <tr style="border-bottom: 1px solid #dde; background: #f8f8f8;">
          <td style="padding: 10px 5px; color: #555; font-size: 14px;">Cumulative CGPA:</td>
          <td style="padding: 10px 5px; font-weight: bold; color: #1a3c6b; font-size: 18px;">{{ cgpa }} / {{ scale }}</td>
        </tr>
        <tr>
          <td style="padding: 10px 5px; color: #555; font-size: 14px;">Classification:</td>
          <td style="padding: 10px 5px; font-weight: bold; color: #27ae60; font-size: 15px;">{{ classification }}</td>
        </tr>
      </table>
    </div>

    <p style="font-size: 14px; color: #555;">
      Log in to your student portal to view your full result slip, download your transcript,
      and check your AI performance prediction.
    </p>

    <!-- CTA Button -->
    <div style="text-align: center; margin: 30px 0;">
      <a href="{{ portal_url }}"
         style="background: #1a3c6b; color: white; padding: 14px 35px;
                text-decoration: none; border-radius: 6px; font-weight: bold;
                font-size: 15px; display: inline-block;">
        View My Results
      </a>
    </div>

    <p style="font-size: 13px; color: #888; border-top: 1px solid #eee; padding-top: 15px; margin-top: 20px;">
      If you have any queries about your results, please contact your Head of Department.
    </p>
  </div>

  <!-- Footer -->
  <div style="background: #333; color: #aaa; padding: 15px; text-align: center; font-size: 12px;">
    This is an automated message. Please do not reply to this email.<br/>
    {{ institution_name }} — Academic Affairs Division
  </div>

</body>
</html>
"""

LOW_GPA_WARNING_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#f9f9f9;">

  <!-- Header -->
  <div style="background: #c0392b; padding: 25px 30px; text-align: center;">
    <h1 style="color: white; margin: 0; font-size: 20px;">⚠ Academic Performance Alert</h1>
    <p style="color: #f5b7b1; margin: 6px 0 0 0; font-size: 14px;">{{ institution_name }}</p>
  </div>

  <!-- Body -->
  <div style="padding: 30px; background: white; border: 1px solid #e0e0e0;">
    <p style="font-size: 15px;">Dear <strong>{{ student_name }}</strong>,</p>

    <p style="font-size: 15px; line-height: 1.7;">
      This is an academic performance notification from {{ institution_name }}.
      Your current Cumulative GPA (CGPA) of
      <strong style="color: #c0392b; font-size: 18px;">{{ cgpa }}</strong>
      places you in the <strong>{{ classification }}</strong> category,
      which requires your immediate attention.
    </p>

    <!-- Warning Box -->
    <div style="background: #fff3cd; border-left: 5px solid #ffc107; padding: 15px 20px; margin: 20px 0; border-radius: 0 6px 6px 0;">
      <strong style="color: #856404;">⚠ Action Required</strong>
      <p style="margin: 8px 0 0 0; color: #856404; font-size: 14px;">
        Please visit your department office or contact your academic advisor
        as soon as possible to discuss your academic improvement plan.
        Early intervention is the most effective way to improve your standing.
      </p>
    </div>

    <p style="font-size: 14px; color: #555;">
      Log in to your student portal to review your results and identify
      courses that need attention.
    </p>

    <div style="text-align: center; margin: 25px 0;">
      <a href="{{ portal_url }}"
         style="background: #c0392b; color: white; padding: 14px 35px;
                text-decoration: none; border-radius: 6px; font-weight: bold;
                font-size: 15px; display: inline-block;">
        View My Results
      </a>
    </div>
  </div>

  <!-- Footer -->
  <div style="background: #333; color: #aaa; padding: 15px; text-align: center; font-size: 12px;">
    This is an automated academic alert. Please do not reply to this email.<br/>
    {{ institution_name }} — Academic Affairs Division
  </div>

</body>
</html>
"""

HOD_SUBMISSION_TEMPLATE = """
Dear {{ hod_name }},

Lecturer {{ lecturer_name }} has submitted results for {{ course_code }} 
({{ student_count }} students) and they are awaiting your review and approval.

Please log in to your HOD dashboard to review and approve the results.

Portal: {{ portal_url }}/hod/dashboard

Regards,
{{ institution_name }} — AcadResult System
"""

REJECTION_NOTIFICATION_TEMPLATE = """
Dear {{ lecturer_name }},

The Head of Department has reviewed your result submission for {{ course_code }}
and has returned it for correction.

Reason: {{ comment }}

Please log in to your lecturer dashboard, make the necessary corrections,
and resubmit the results.

Portal: {{ portal_url }}/lecturer/dashboard

Regards,
{{ institution_name }} — AcadResult System
"""


# ── Sending Functions ──────────────────────────────────────────────────────────

def _send_email(subject, recipients, html_body=None, text_body=None):
    """
    Core email sending function.
    Returns True if sent successfully, False otherwise.
    In development mode (MAIL_SUPPRESS_SEND=True), prints to console instead.
    """
    try:
        msg = Message(
            subject=subject,
            recipients=recipients if isinstance(recipients, list) else [recipients],
        )
        if html_body:
            msg.html = html_body
        if text_body:
            msg.body = text_body

        mail.send(msg)
        current_app.logger.info(f"Email sent: '{subject}' → {recipients}")
        return True

    except Exception as e:
        current_app.logger.error(f"Email failed: '{subject}' → {recipients} | Error: {e}")
        # In dev mode print to console so you can see what would have been sent
        if current_app.config.get("MAIL_SUPPRESS_SEND"):
            print(f"\n[EMAIL PREVIEW] To: {recipients}")
            print(f"[EMAIL PREVIEW] Subject: {subject}")
            if text_body:
                print(f"[EMAIL PREVIEW] Body: {text_body[:200]}...")
            print()
        return False


def send_result_notification(student, session_name, semester,
                              gpa, cgpa, classification):
    """
    Notify student that their results have been approved and released.

    Args:
        student     : Student model instance
        session_name: e.g. "2024/2025"
        semester    : 1 or 2
        gpa         : float semester GPA
        cgpa        : float cumulative GPA
        classification: e.g. "Distinction", "Upper Credit"
    """
    try:
        institution = current_app.config.get("INSTITUTION_NAME", "Temple Gate Polytechnic Aba")
        portal_url  = current_app.config.get("PORTAL_URL", "http://localhost:5000")
        scale       = student.grading_scale

        html_body = render_template_string(
            RESULT_RELEASED_TEMPLATE,
            student_name   = student.user.full_name,
            session_name   = session_name,
            semester       = semester,
            gpa            = f"{gpa:.2f}",
            cgpa           = f"{cgpa:.2f}",
            scale          = scale,
            classification = classification,
            portal_url     = f"{portal_url}/student/dashboard",
            institution_name = institution,
        )

        return _send_email(
            subject    = f"Results Released — {session_name} Semester {semester} | {institution}",
            recipients = student.user.email,
            html_body  = html_body,
        )

    except Exception as e:
        current_app.logger.error(f"send_result_notification failed: {e}")
        return False


def send_low_gpa_warning(student, cgpa, classification):
    """
    Send academic performance warning to a student with low CGPA.
    Triggered when classification is 'Probation/Fail' or 'Fail'.
    """
    try:
        institution = current_app.config.get("INSTITUTION_NAME", "Temple Gate Polytechnic Aba")
        portal_url  = current_app.config.get("PORTAL_URL", "http://localhost:5000")

        html_body = render_template_string(
            LOW_GPA_WARNING_TEMPLATE,
            student_name     = student.user.full_name,
            cgpa             = f"{cgpa:.2f}",
            classification   = classification,
            portal_url       = f"{portal_url}/student/dashboard",
            institution_name = institution,
        )

        return _send_email(
            subject    = f"⚠ Academic Performance Warning | {institution}",
            recipients = student.user.email,
            html_body  = html_body,
        )

    except Exception as e:
        current_app.logger.error(f"send_low_gpa_warning failed: {e}")
        return False


def send_hod_submission_notification(hod_email, lecturer_name,
                                     course_code, student_count):
    """Notify HOD when a lecturer submits results for review."""
    try:
        institution = current_app.config.get("INSTITUTION_NAME", "Temple Gate Polytechnic Aba")
        portal_url  = current_app.config.get("PORTAL_URL", "http://localhost:5000")

        from app.models.user import User
        hod_user = User.query.filter_by(email=hod_email).first()
        hod_name = hod_user.full_name if hod_user else "HOD"

        text_body = render_template_string(
            HOD_SUBMISSION_TEMPLATE,
            hod_name         = hod_name,
            lecturer_name    = lecturer_name,
            course_code      = course_code,
            student_count    = student_count,
            portal_url       = portal_url,
            institution_name = institution,
        )

        return _send_email(
            subject    = f"Results Submitted for Review — {course_code} | {institution}",
            recipients = hod_email,
            text_body  = text_body,
        )

    except Exception as e:
        current_app.logger.error(f"send_hod_submission_notification failed: {e}")
        return False


def send_rejection_notification(lecturer_email, lecturer_name,
                                 course_code, comment):
    """
    Notify lecturer when HOD rejects their result submission.
    This ensures lecturers know to correct and resubmit.
    """
    try:
        institution = current_app.config.get("INSTITUTION_NAME", "Temple Gate Polytechnic Aba")
        portal_url  = current_app.config.get("PORTAL_URL", "http://localhost:5000")

        text_body = render_template_string(
            REJECTION_NOTIFICATION_TEMPLATE,
            lecturer_name    = lecturer_name,
            course_code      = course_code,
            comment          = comment,
            portal_url       = portal_url,
            institution_name = institution,
        )

        return _send_email(
            subject    = f"Result Submission Returned — {course_code} | {institution}",
            recipients = lecturer_email,
            text_body  = text_body,
        )

    except Exception as e:
        current_app.logger.error(f"send_rejection_notification failed: {e}")
        return False


def send_bulk_result_notifications(student_list, session_name, semester):
    """
    Send result notifications to multiple students at once.
    Called after HOD batch approval.

    Args:
        student_list: list of dicts with keys:
                      student, gpa, cgpa, classification
        session_name: e.g. "2024/2025"
        semester    : 1 or 2
    """
    sent    = 0
    failed  = 0

    for item in student_list:
        success = send_result_notification(
            student        = item["student"],
            session_name   = session_name,
            semester       = semester,
            gpa            = item["gpa"],
            cgpa           = item["cgpa"],
            classification = item["classification"],
        )
        if success:
            sent += 1
        else:
            failed += 1

        # Send warning if at risk
        at_risk_labels = ("Probation/Fail", "Fail", "Third Class")
        if item["classification"] in at_risk_labels:
            send_low_gpa_warning(
                item["student"],
                item["cgpa"],
                item["classification"]
            )

    current_app.logger.info(
        f"Bulk notifications: {sent} sent, {failed} failed for "
        f"{session_name} Sem {semester}"
    )
    return {"sent": sent, "failed": failed}
