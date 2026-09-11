/**
 * Row shapes returned by the academic-structure endpoints.
 *
 * These mirror the backend schemas in `app/schemas/`; where a name differs it
 * is because `class` is a reserved word in both languages.
 */

export interface Program {
  id: string;
  name: string;
  code: string;
  created_by_id: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface ProgramWrite {
  name: string;
  code: string;
}

export interface ClassRow {
  id: string;
  name: string;
  program_id: string;
  program_name: string;
  program_code: string;
  created_at: string;
}

export interface ClassCreate {
  name: string;
  program_id: string;
}

export interface ClassUpdate {
  name?: string;
  program_id?: string;
}

export interface SubjectClassRef {
  id: string;
  name: string;
  program_id: string;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  teacher_id: string | null;
  teacher_name: string | null;
  teacher_designation: string | null;
  student_limit: number;
  student_count: number;
  seats_available: number;
  classes: SubjectClassRef[];
  created_at: string;
}

export interface SubjectCreate {
  name: string;
  code: string;
  student_limit?: number;
  teacher_id?: string | null;
  class_ids?: string[];
}

export interface SubjectUpdate {
  name?: string;
  code?: string;
  student_limit?: number;
  /** `null` clears the assignment, which is different from omitting it. */
  teacher_id?: string | null;
}

// ----- attendance ----------------------------------------------------------

export type AttendanceStatus = 'present' | 'absent' | 'leave';

export const ATTENDANCE_STATUSES: AttendanceStatus[] = ['present', 'absent', 'leave'];

export interface AttendanceCounts {
  present: number;
  absent: number;
  leave: number;
  unmarked: number;
  total: number;
}

export interface AttendanceClassRef {
  id: string;
  name: string;
  program_id: string;
  program_code: string;
}

export interface AttendanceSummary {
  id: string;
  /** `class` is a keyword, so the API's key is quoted here. */
  class: AttendanceClassRef;
  date: string;
  marked_by_id: string | null;
  counts: AttendanceCounts;
  created_at: string;
}

export interface AttendanceStudentRef {
  id: string;
  roll_no: string;
  first_name: string;
  last_name: string;
}

export interface AttendanceMark {
  student: AttendanceStudentRef;
  /** Null means unmarked — nobody has called this student yet. */
  status: AttendanceStatus | null;
  note: string | null;
  marked_by_id: string | null;
  marked_at: string | null;
  /** The student has since left the class; the mark is kept and flagged. */
  off_roster: boolean;
}

export interface AttendanceSheet extends AttendanceSummary {
  marks: AttendanceMark[];
}

export interface MarkInput {
  student_id: string;
  status: AttendanceStatus | null;
  note?: string | null;
}

// ----- students ------------------------------------------------------------

export interface SessionRow {
  id: string;
  start_year: number;
  end_year: number;
  label: string;
  student_count: number;
  created_at: string;
}

/** The class a student is in, as embedded in a student row. */
export interface StudentEnrollment {
  id: string;
  class_id: string;
  class_name: string;
  program_id: string;
  program_code: string;
  subject_count: number;
}

export interface Student {
  id: string;
  roll_no: string;
  session: { id: string; label: string; start_year: number; end_year: number };
  enrollment: StudentEnrollment | null;

  first_name: string;
  last_name: string;
  full_name: string;
  b_form_cnic: string | null;
  date_of_birth: string | null;

  father_name: string | null;
  father_cnic: string | null;
  mother_name: string | null;
  guardian_cell_no: string | null;

  cell_no: string | null;
  address: string | null;
  province: string | null;
  domicile_district: string | null;

  last_school_name: string | null;
  ssc_roll_no: string | null;
  ssc_marks_obtained: number | null;
  ssc_marks_total: number | null;
  ssc_year: number | null;
  ssc_percentage: number | null;

  email: string | null;
  is_active: boolean;
  has_password: boolean;
  /** What still has to be collected before the file is complete. */
  missing_fields: string[];
  created_at: string;
}

/** Everything optional at admission; only name and session are required. */
export interface StudentDetails {
  b_form_cnic?: string | null;
  date_of_birth?: string | null;
  father_name?: string | null;
  father_cnic?: string | null;
  mother_name?: string | null;
  guardian_cell_no?: string | null;
  cell_no?: string | null;
  address?: string | null;
  province?: string | null;
  domicile_district?: string | null;
  last_school_name?: string | null;
  ssc_roll_no?: string | null;
  ssc_marks_obtained?: number | null;
  ssc_marks_total?: number | null;
  ssc_year?: number | null;
  email?: string | null;
}

export interface StudentCreate extends StudentDetails {
  session_id: string;
  first_name: string;
  last_name: string;
  password?: string | null;
}

export interface StudentUpdate extends StudentDetails {
  first_name?: string;
  last_name?: string;
  is_active?: boolean;
}

// ----- enrollment ----------------------------------------------------------

export interface EnrollmentSubjectRef {
  id: string;
  name: string;
  code: string;
}

export interface Enrollment {
  id: string;
  student: { id: string; roll_no: string; first_name: string; last_name: string };
  class: {
    id: string;
    name: string;
    program_id: string;
    program_name: string;
    program_code: string;
  };
  subjects: EnrollmentSubjectRef[];
  enrolled_at: string;
  created_at: string;
}

export interface EnrollmentCreate {
  student_id: string;
  class_id: string;
  subject_ids?: string[];
}

/**
 * A move to another class, and what it cost.
 *
 * Every subject belonged to the old class, so a move drops all of them; the
 * count comes back so the screen can say so rather than leaving it to be
 * noticed later.
 */
export interface EnrollmentMoveResult {
  enrollment: Enrollment;
  dropped_subjects: number;
}

// ----- faculty -------------------------------------------------------------

export interface Faculty {
  id: string;
  employee_no: string;
  first_name: string;
  last_name: string;
  full_name: string;
  designation: string | null;
  qualification: string | null;
  cnic: string | null;
  email: string | null;
  cell_no: string | null;
  address: string | null;
  joined_on: string | null;
  /** The staff account this person signs in with, if linked. */
  user_id: string | null;
  is_active: boolean;
  /** What still has to be collected before the file is complete. */
  missing_fields: string[];
  created_at: string;
}

export interface StaffUserRow {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  roles: string[];
}

export interface FacultyWrite {
  employee_no?: string;
  first_name?: string;
  last_name?: string;
  designation?: string | null;
  qualification?: string | null;
  cnic?: string | null;
  email?: string | null;
  cell_no?: string | null;
  address?: string | null;
  joined_on?: string | null;
  user_id?: string | null;
  is_active?: boolean;
}

// ----- roles and permissions ------------------------------------------------

export interface Role {
  id: string;
  name: string;
  description: string | null;
  /** Permission codes this role carries. */
  permissions: string[];
  /** Seeded roles the API refuses to rename, delete or edit permissions on. */
  is_system: boolean;
}

export interface PermissionRow {
  id: string;
  code: string;
  description: string | null;
}

export interface RoleCreate {
  name: string;
  description?: string | null;
  permissions?: string[];
}

export interface RoleUpdate {
  name?: string;
  description?: string | null;
}

// ----- exams ---------------------------------------------------------------

export type ExamScope = 'subject' | 'class';

export interface ExamPaper {
  id: string;
  subject_id: string;
  subject_name: string;
  subject_code: string;
  total_marks: number;
  teacher_id: string | null;
  teacher_name: string | null;
  /** How many students have a mark recorded. */
  marked: number;
}

export interface Exam {
  id: string;
  title: string;
  date: string;
  scope: ExamScope;
  class: { id: string; name: string; program_id: string; program_code: string };
  papers: ExamPaper[];
  created_by_id: string | null;
  created_at: string;
}

export interface ExamCreate {
  class_id: string;
  title: string;
  date: string;
  scope: ExamScope;
  subject_id?: string | null;
  total_marks?: number;
}

export interface ExamUpdate {
  title?: string;
  date?: string;
}

export interface ExamMark {
  student: { id: string; roll_no: string; first_name: string; last_name: string };
  /** Null means nobody has entered a mark yet — not a zero. */
  obtained: number | null;
  is_absent: boolean;
  marked_by_id: string | null;
  marked_at: string | null;
}

export interface MarkSheet {
  paper: ExamPaper;
  exam_id: string;
  exam_title: string;
  date: string;
  class_name: string;
  /** Whether this caller may edit it — the subject's teacher, or an override. */
  can_mark: boolean;
  marks: ExamMark[];
}

/** Named for exams: attendance already has a `MarkInput` of its own shape. */
export interface ExamMarkInput {
  student_id: string;
  obtained?: number | null;
  is_absent?: boolean;
}
