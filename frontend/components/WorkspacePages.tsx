"use client";

import {
  AlarmClock,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  FolderArchive,
  LibraryBig,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import {
  type Analytics,
  type DashboardCourse,
  type DashboardOverview,
  type LibraryOverview,
  API_BASE,
  getDashboardOverview,
  getFocusAnalytics,
  getLibraryOverview,
} from "@/lib/api";

const demoOverview: DashboardOverview = {
  semester_label: "Semester 2 · 2026",
  course_count: 4,
  semester_progress_percent: 61,
  courses: [
    { id: 1, name: "Data Mining", course_code: "COMP90051", term_name: "Semester 2", assignment_total: 6, assignment_completed: 3, semester_progress_percent: 61, next_due_at: "2026-09-22T23:59:00+10:00" },
    { id: 2, name: "Human Computer Interaction", course_code: "INFO30005", term_name: "Semester 2", assignment_total: 5, assignment_completed: 3, semester_progress_percent: 61, next_due_at: "2026-09-24T17:00:00+10:00" },
    { id: 3, name: "Algorithms", course_code: "COMP90038", term_name: "Semester 2", assignment_total: 7, assignment_completed: 5, semester_progress_percent: 61, next_due_at: "2026-09-28T23:59:00+10:00" },
    { id: 4, name: "Visualisation", course_code: "INFO30009", term_name: "Semester 2", assignment_total: 4, assignment_completed: 2, semester_progress_percent: 61, next_due_at: null },
  ],
  deadlines: [
    { id: 1, course_id: 1, course_name: "Data Mining", title: "Project report", due_at: "2026-09-22T23:59:00+10:00", status: "unsubmitted" },
    { id: 2, course_id: 2, course_name: "Human Computer Interaction", title: "Prototype critique", due_at: "2026-09-24T17:00:00+10:00", status: "unsubmitted" },
  ],
  today_schedule: [
    { id: 1, course_id: 2, course_name: "Human Computer Interaction", title: "Studio", start_at: "2026-09-21T10:00:00+10:00", end_at: "2026-09-21T12:00:00+10:00", location: "Babel 305" },
    { id: 2, course_id: 1, course_name: "Data Mining", title: "Lecture", start_at: "2026-09-21T14:00:00+10:00", end_at: "2026-09-21T16:00:00+10:00", location: "Theatre 1" },
  ],
};

const demoLibrary: LibraryOverview = {
  total_materials: 12,
  total_flashcards: 36,
  courses: [
    { id: 1, name: "Data Mining", course_code: "COMP90051", material_count: 6, flashcard_count: 18, materials: [{ id: 1, name: "Week 04 · Evaluation.pdf", week: "Week 04", category: "Lecture", size_bytes: 1_800_000, updated_at: "2026-09-20T10:00:00+10:00" }, { id: 2, name: "Project rubric.pdf", week: "Assessment", category: "Assessment", size_bytes: 420_000, updated_at: "2026-09-19T10:00:00+10:00" }] },
    { id: 2, name: "Human Computer Interaction", course_code: "INFO30005", material_count: 6, flashcard_count: 18, materials: [{ id: 3, name: "Week 03 · Prototyping.pdf", week: "Week 03", category: "Studio", size_bytes: 2_100_000, updated_at: "2026-09-18T10:00:00+10:00" }] },
  ],
};

const demoAnalytics: Analytics = {
  total_seconds: 2 * 3600 + 14 * 60,
  by_course: [],
  daily: [
    { date: "Mon", seconds: 2100 }, { date: "Tue", seconds: 3600 }, { date: "Wed", seconds: 1800 },
    { date: "Thu", seconds: 4200 }, { date: "Fri", seconds: 2640 }, { date: "Sat", seconds: 0 }, { date: "Sun", seconds: 0 },
  ],
};

function useOverview() {
  const [overview, setOverview] = useState<DashboardOverview>(demoOverview);
  const [live, setLive] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void getDashboardOverview().then((value) => {
      if (!cancelled && value.course_count > 0) { setOverview(value); setLive(true); }
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);
  return { overview, live };
}

function formatTime(value: string | null, mounted: boolean) {
  if (!value || !mounted) return "—";
  return new Intl.DateTimeFormat("en-AU", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Australia/Melbourne" }).format(new Date(value));
}

function formatDate(value: string | null, mounted: boolean) {
  if (!value || !mounted) return "No due date";
  return new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", timeZone: "Australia/Melbourne" }).format(new Date(value));
}

function relativeDeadline(value: string | null, mounted: boolean) {
  if (!value || !mounted) return "No deadline";
  const hours = Math.round((new Date(value).getTime() - Date.now()) / 3_600_000);
  if (hours <= 0) return "Overdue";
  return hours < 24 ? `${hours}h remaining` : `${Math.ceil(hours / 24)}d remaining`;
}

function courseProgress(course: DashboardCourse) {
  if (course.semester_progress_percent !== null) return course.semester_progress_percent;
  return course.assignment_total ? Math.round((course.assignment_completed / course.assignment_total) * 100) : 0;
}

function PageHeading({ index, eyebrow, title, description, children }: { index: string; eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow"><span>{index}</span>{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{children}</div>;
}

export function OverviewPage() {
  const { overview, live } = useOverview();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const urgent = overview.deadlines[0];
  const completed = overview.courses.reduce((total, course) => total + course.assignment_completed, 0);
  const assignments = overview.courses.reduce((total, course) => total + course.assignment_total, 0);

  return <div className="page-content overview-page">
    <PageHeading index="01" eyebrow={overview.semester_label.toUpperCase()} title="Semester, at a glance." description="The immediate work, today’s room-and-time plan, and a clean view of where each course stands.">
      <span className={`data-source ${live ? "data-source-live" : ""}`}>{live ? "LIVE CANVAS DATA" : "DEMO UNTIL SYNC"}</span>
    </PageHeading>
    <section className="semester-strip" aria-label="当前学期进度">
      <div><span>TERM HORIZON</span><strong>{overview.semester_progress_percent ?? "—"}<small>{overview.semester_progress_percent === null ? " connect dates to calculate" : "% complete"}</small></strong></div>
      <div className="horizon-track"><span style={{ width: `${overview.semester_progress_percent ?? 0}%` }} /></div>
      <div className="semester-stats"><span><strong>{overview.course_count}</strong> courses</span><span><strong>{completed}/{assignments || "—"}</strong> assessments submitted</span></div>
    </section>
    <div className="overview-grid">
      <section className="deadline-feature">
        <div className="feature-kicker"><AlarmClock size={16} /> NEAREST DEADLINE</div>
        {urgent ? <><div className="deadline-time">{relativeDeadline(urgent.due_at, mounted)}</div><h2>{urgent.title}</h2><p>{urgent.course_name} · due {formatDate(urgent.due_at, mounted)} at {formatTime(urgent.due_at, mounted)}</p><Link href="/calendar" className="inline-action">See all deadlines <ArrowUpRight size={15} /></Link></> : <><div className="deadline-time calm">Clear horizon</div><h2>No pending deadlines.</h2><p>Your Canvas mirror has no unsubmitted work with a due date.</p></>}
      </section>
      <section className="panel schedule-summary">
        <div className="panel-heading"><div><span className="section-index">02</span><h2>Today&apos;s timetable</h2></div><CalendarDays size={18} className="panel-icon" /></div>
        <div className="timeline-list">{overview.today_schedule.length ? overview.today_schedule.map((event) => <div className="timeline-item" key={event.id ?? event.title}><time>{formatTime(event.start_at, mounted)}</time><span><strong>{event.title}</strong><small>{event.course_name ?? "Canvas event"}{event.location ? ` · ${event.location}` : ""}</small></span></div>) : <div className="empty-state">No scheduled class today. Use the open space intentionally.</div>}</div>
        <Link href="/calendar" className="quiet-link">Open full calendar <ChevronRight size={14} /></Link>
      </section>
      <section className="panel course-ledger">
        <div className="panel-heading"><div><span className="section-index">03</span><h2>This year&apos;s courses</h2></div><span className="muted-count">{overview.course_count} active</span></div>
        <div className="course-ledger-list">{overview.courses.map((course) => <div className="course-ledger-row" key={course.id ?? course.name}><div className="course-identity"><span>{course.course_code ?? "CANVAS"}</span><strong>{course.name}</strong></div><div className="course-meter"><div><span style={{ width: `${courseProgress(course)}%` }} /></div><small>{courseProgress(course)}% through term</small></div><div className="course-assessment"><strong>{course.assignment_completed}/{course.assignment_total || "—"}</strong><small>submitted</small></div><div className="course-next"><small>NEXT</small><strong>{formatDate(course.next_due_at, mounted)}</strong></div></div>)}</div>
      </section>
    </div>
  </div>;
}

export function CalendarPage() {
  const { overview } = useOverview();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return <div className="page-content calendar-page">
    <PageHeading index="02" eyebrow="PLAN THE WEEK" title="Calendar, without the noise." description="Your class meetings and outstanding Canvas due dates are kept in the same visual rhythm.">
      <a href={`${API_BASE}/api/calendar/feed.ics`} className="outline-action"><Download size={15} /> Export .ics</a>
    </PageHeading>
    <section className="calendar-banner"><div><span>SUBSCRIBE ONCE</span><h2>Use the iCalendar feed in Apple, Google, or Outlook Calendar.</h2></div><code>{API_BASE.replace(/^http/, "webcal")}/api/calendar/feed.ics</code></section>
    <div className="calendar-columns">
      <section className="panel day-agenda"><div className="panel-heading"><div><span className="section-index">TODAY</span><h2>Classes & events</h2></div><Clock3 size={18} className="panel-icon" /></div><div className="agenda-list">{overview.today_schedule.length ? overview.today_schedule.map((event) => <article className="agenda-event" key={event.id ?? event.title}><time>{formatTime(event.start_at, mounted)}<small>{event.end_at ? formatTime(event.end_at, mounted) : ""}</small></time><div><strong>{event.title}</strong><p>{event.course_name ?? "Canvas event"}</p>{event.location && <span>{event.location}</span>}</div></article>) : <div className="empty-state">Nothing scheduled for today.</div>}</div></section>
      <section className="panel deadline-agenda"><div className="panel-heading"><div><span className="section-index">NEXT UP</span><h2>Deadline runway</h2></div><AlarmClock size={18} className="orange-icon" /></div><div className="deadline-agenda-list">{overview.deadlines.length ? overview.deadlines.map((deadline) => <article key={deadline.id ?? deadline.title}><div><span>{formatDate(deadline.due_at, mounted)}</span><strong>{deadline.title}</strong><small>{deadline.course_name}</small></div><em>{relativeDeadline(deadline.due_at, mounted)}</em></article>) : <div className="empty-state">No upcoming Canvas deadlines.</div>}</div></section>
    </div>
  </div>;
}

export function LibraryPage() {
  const [library, setLibrary] = useState<LibraryOverview>(demoLibrary);
  const [live, setLive] = useState(false);
  useEffect(() => { let cancelled = false; void getLibraryOverview().then((value) => { if (!cancelled && value.total_materials > 0) { setLibrary(value); setLive(true); } }).catch(() => undefined); return () => { cancelled = true; }; }, []);
  return <div className="page-content library-page">
    <PageHeading index="03" eyebrow="MATERIALS & MEMORY" title="Your course library." description="Canvas files are organised by course, ready to archive locally or turn into lightweight revision cards.">
      <span className={`data-source ${live ? "data-source-live" : ""}`}>{live ? `${library.total_materials} SYNCED FILES` : "DEMO UNTIL SYNC"}</span>
    </PageHeading>
    <section className="library-stats"><div><FolderArchive size={21} /><strong>{library.total_materials}</strong><span>course materials</span></div><div><Sparkles size={21} /><strong>{library.total_flashcards}</strong><span>AI revision cards</span></div><div><BookOpen size={21} /><strong>{library.courses.length}</strong><span>course collections</span></div></section>
    <div className="library-course-list">{library.courses.map((course) => <section className="panel library-course" key={course.id ?? course.name}><div className="library-course-head"><div><span>{course.course_code ?? "CANVAS"}</span><h2>{course.name}</h2></div><div className="library-actions">{course.id && <><a href={`${API_BASE}/api/courses/${course.id}/materials.zip`} title="下载课件压缩包"><FolderArchive size={16} /> ZIP</a><a href={`${API_BASE}/api/courses/${course.id}/flashcards.anki`} title="导出 Anki 卡片"><Sparkles size={16} /> ANKI</a></>}</div></div><div className="material-summary"><span>{course.material_count} files</span><span>{course.flashcard_count} flashcards</span></div><div className="material-list">{course.materials.length ? course.materials.map((material) => <div className="material-row" key={material.id ?? material.name}><FileText size={17} /><div><strong>{material.name}</strong><small>{material.week ?? "Course material"}{material.category ? ` · ${material.category}` : ""}</small></div><span>{material.size_bytes ? `${Math.round(material.size_bytes / 1024)} KB` : ""}</span></div>) : <div className="empty-state">No files synchronised for this course yet.</div>}</div></section>)}</div>
  </div>;
}

export function ProgressPage() {
  const { overview } = useOverview();
  const [analytics, setAnalytics] = useState<Analytics>(demoAnalytics);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); void getFocusAnalytics().then((value) => { if (value.total_seconds > 0) setAnalytics(value); }).catch(() => undefined); }, []);
  const hours = (analytics.total_seconds / 3600).toFixed(1);
  const courseData = useMemo(() => overview.courses.map((course) => ({ name: course.course_code ?? course.name, progress: courseProgress(course), submitted: `${course.assignment_completed}/${course.assignment_total}` })), [overview]);
  return <div className="page-content progress-page">
    <PageHeading index="04" eyebrow="LEARNING SIGNALS" title="Progress with context." description="Match your time investment to the assessments and semester runway that still matter.">
      <Link href="/" className="outline-action"><Target size={15} /> View semester plan</Link>
    </PageHeading>
    <div className="progress-summary"><section className="progress-total"><span>THIS WEEK</span><strong>{hours}<small> hours focused</small></strong><p>{overview.semester_progress_percent ?? "—"}% of the semester has elapsed.</p></section><section className="panel focus-chart"><div className="panel-heading"><div><span className="section-index">FOCUS TREND</span><h2>Daily deep work</h2></div><TrendingUp size={18} className="mint-icon" /></div><div className="progress-chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={analytics.daily}><defs><linearGradient id="progressFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#bce7d3" stopOpacity={0.6} /><stop offset="100%" stopColor="#bce7d3" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#e5e1d7" /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "#8993a1", fontSize: 10 }} /><YAxis hide /><Tooltip formatter={(value) => [`${Math.round(Number(value) / 60)}m`, "focus"]} /><Area type="monotone" dataKey="seconds" stroke="#6cac8f" fill="url(#progressFill)" strokeWidth={2.5} /></AreaChart></ResponsiveContainer></div></section></div>
    <section className="panel progress-courses"><div className="panel-heading"><div><span className="section-index">COURSE RUNWAY</span><h2>Course progress</h2></div><span className="muted-count">{overview.course_count} courses</span></div><div className="progress-course-list">{courseData.map((course) => <div key={course.name}><div><strong>{course.name}</strong><span>{course.submitted} submitted</span></div><div className="course-meter"><div><span style={{ width: `${course.progress}%` }} /></div><small>{course.progress}% term progress</small></div></div>)}</div><p className="fine-print">Course runway uses Canvas start and end dates when available; otherwise it uses assessment completion.</p></section>
    {!mounted && <span className="sr-only">Loading time-based progress data</span>}
  </div>;
}
