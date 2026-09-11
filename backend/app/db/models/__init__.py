"""Import every model so ``Base.metadata`` is fully populated.

Importing this package (done by the app and by Alembic's ``env.py``) is what
registers all tables for autogenerate and ``create_all``.
"""

from app.db.models.academic_session import AcademicSession
from app.db.models.attendance import AttendanceRecord, AttendanceSheet
from app.db.models.class_ import Class
from app.db.models.enrollment import Enrollment, SubjectEnrollment
from app.db.models.exam import Exam, ExamMark, ExamSubject
from app.db.models.faculty import Faculty
from app.db.models.program import Program
from app.db.models.rbac import Permission, Role, role_permissions, user_roles
from app.db.models.session import RefreshSession
from app.db.models.student import Student
from app.db.models.subject import Subject, class_subjects
from app.db.models.user import User

__all__ = [
    "User",
    "RefreshSession",
    "Role",
    "Permission",
    "user_roles",
    "role_permissions",
    "Student",
    "AcademicSession",
    "Faculty",
    "Program",
    "Class",
    "Subject",
    "class_subjects",
    "Enrollment",
    "SubjectEnrollment",
    "AttendanceSheet",
    "AttendanceRecord",
    "Exam",
    "ExamSubject",
    "ExamMark",
]
