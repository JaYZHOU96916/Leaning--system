export type TodoItem = {
  key: string;
  kind: "deadline" | "schedule" | "manual";
  title: string;
  course_id: number | null;
  assignment_id: number | null;
  due_at: string | null;
  priority: number;
  status: string;
};

export type FocusState = {
  id: number;
  course_id: number | null;
  assignment_id: number | null;
  status: "running" | "paused" | "completed";
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
};

export type Analytics = {
  total_seconds: number;
  by_course: { course: string; seconds: number }[];
  daily: { date: string; seconds: number }[];
};

export type DashboardDeadline = {
  id: number | null;
  course_id: number;
  course_name: string;
  title: string;
  due_at: string | null;
  status: string;
};

export type DashboardScheduleEvent = {
  id: number | null;
  course_id: number | null;
  course_name: string | null;
  title: string;
  start_at: string;
  end_at: string | null;
  location: string | null;
};

export type DashboardCourse = {
  id: number | null;
  name: string;
  course_code: string | null;
  term_name: string | null;
  assignment_total: number;
  assignment_completed: number;
  semester_progress_percent: number | null;
  next_due_at: string | null;
};

export type DashboardOverview = {
  semester_label: string;
  course_count: number;
  semester_progress_percent: number | null;
  courses: DashboardCourse[];
  deadlines: DashboardDeadline[];
  today_schedule: DashboardScheduleEvent[];
};

export type LibraryMaterial = {
  id: number | null;
  name: string;
  week: string | null;
  category: string | null;
  size_bytes: number | null;
  updated_at: string | null;
};

export type LibraryCourse = {
  id: number | null;
  name: string;
  course_code: string | null;
  material_count: number;
  flashcard_count: number;
  materials: LibraryMaterial[];
};

export type LibraryOverview = {
  courses: LibraryCourse[];
  total_materials: number;
  total_flashcards: number;
};

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const API_DOCS_URL = `${API_BASE}/docs`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function getTodayTodos() {
  return request<{ items: TodoItem[] }>("/api/todos/today");
}

export async function getDashboardOverview() {
  return request<DashboardOverview>("/api/dashboard/overview");
}

export async function getLibraryOverview() {
  return request<LibraryOverview>("/api/dashboard/library");
}

export async function getFocusAnalytics() {
  return request<Analytics>("/api/analytics/focus");
}

export async function getActiveFocus() {
  return request<{ focus: FocusState | null }>("/api/focus/active");
}

export async function startFocus(payload: { course_id?: number | null; assignment_id?: number | null }) {
  return request<FocusState>("/api/focus/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function mutateFocus(id: number, action: "pause" | "resume" | "complete") {
  return request<FocusState>(`/api/focus/${id}/${action}`, { method: "POST" });
}

export async function getGradeWhatIf(target_percent: number) {
  return request<{ required_average_percent: string | null; max_possible_percent: string }>(
    "/api/courses/1/grades/what-if",
    { method: "POST", body: JSON.stringify({ target_percent }) },
  );
}
