"use client";

import {
  AlarmClock,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Flame,
  Gauge,
  GraduationCap,
  LayoutGrid,
  Library,
  ListChecks,
  Menu,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
  Target,
  TimerReset,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  type Analytics,
  type FocusState,
  type TodoItem,
  getActiveFocus,
  getFocusAnalytics,
  getGradeWhatIf,
  getTodayTodos,
  mutateFocus,
  startFocus,
} from "@/lib/api";

const demoTodos: TodoItem[] = [
  {
    key: "demo:1",
    kind: "deadline",
    title: "Data Mining · Project report",
    course_id: 1,
    assignment_id: 1,
    due_at: new Date(Date.now() + 1000 * 60 * 60 * 18).toISOString(),
    priority: 1000,
    status: "unsubmitted",
  },
  {
    key: "demo:2",
    kind: "schedule",
    title: "Human Computer Interaction · Studio",
    course_id: 2,
    assignment_id: null,
    due_at: new Date(Date.now() + 1000 * 60 * 60 * 3).toISOString(),
    priority: 800,
    status: "scheduled",
  },
  {
    key: "demo:3",
    kind: "manual",
    title: "Outline the literature review",
    course_id: 1,
    assignment_id: null,
    due_at: null,
    priority: 20,
    status: "open",
  },
];

const demoAnalytics: Analytics = {
  total_seconds: 2 * 60 * 60 + 14 * 60,
  by_course: [
    { course: "Data Mining", seconds: 4200 },
    { course: "HCI Studio", seconds: 2880 },
    { course: "Algorithms", seconds: 1560 },
  ],
  daily: [
    { date: "Mon", seconds: 2100 },
    { date: "Tue", seconds: 3600 },
    { date: "Wed", seconds: 1800 },
    { date: "Thu", seconds: 4200 },
    { date: "Fri", seconds: 2640 },
    { date: "Sat", seconds: 0 },
    { date: "Sun", seconds: 0 },
  ],
};

const flashcards = [
  {
    tag: "Data Mining / Week 04",
    question: "What does a precision–recall trade-off describe?",
    answer: "Increasing precision often reduces recall: the threshold determines whether the model prefers fewer confident positives or a wider capture of positives.",
  },
  {
    tag: "HCI Studio / Week 03",
    question: "Why test a prototype before polishing it?",
    answer: "Early tests reveal whether the interaction model works before visual detail makes the wrong direction expensive to change.",
  },
];

function formatDuration(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function formatDue(dueAt: string | null, hydrated: boolean) {
  if (!dueAt) return "今天内";
  if (!hydrated) return "—";
  const diff = new Date(dueAt).getTime() - Date.now();
  const hours = Math.round(diff / (1000 * 60 * 60));
  if (hours <= 0) return "已逾期";
  if (hours < 24) return `${hours}h left`;
  return `${Math.round(hours / 24)}d left`;
}

function formatScheduleTime(dueAt: string | null, hydrated: boolean) {
  if (!dueAt || !hydrated) return "—";
  return new Date(dueAt).toLocaleTimeString("en-AU", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Australia/Melbourne",
  });
}

function kindIcon(kind: TodoItem["kind"]) {
  if (kind === "deadline") return <Flame size={15} />;
  if (kind === "schedule") return <CalendarDays size={15} />;
  return <ListChecks size={15} />;
}

function navIcon(label: string) {
  if (label === "Today") return <LayoutGrid size={19} />;
  if (label === "Calendar") return <CalendarDays size={19} />;
  if (label === "Library") return <Library size={19} />;
  return <Gauge size={19} />;
}

function CircularTimer({ seconds, running }: { seconds: number; running: boolean }) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  const progress = ((25 * 60 - seconds) / (25 * 60)) * 360;
  return (
    <div
      className={`timer-orb ${running ? "timer-orb-running" : ""}`}
      style={{ background: `conic-gradient(#ff704a ${progress}deg, #2e3a4b ${progress}deg 360deg)` }}
      aria-label={`专注计时 ${minutes}:${remainder}`}
    >
      <div className="timer-orb-inner">
        <span className="timer-kicker">FOCUS / 25</span>
        <strong>{minutes}:{remainder}</strong>
        <span className="timer-state">{running ? "in the zone" : "ready when you are"}</span>
      </div>
    </div>
  );
}

export function AcademicDashboard() {
  const [todos, setTodos] = useState<TodoItem[]>(demoTodos);
  const [analytics, setAnalytics] = useState<Analytics>(demoAnalytics);
  const [focus, setFocus] = useState<FocusState | null>(null);
  const [timerSeconds, setTimerSeconds] = useState(25 * 60);
  const [selectedTodo, setSelectedTodo] = useState<TodoItem>(demoTodos[0]);
  const [syncLabel, setSyncLabel] = useState("Canvas linked");
  const [targetGrade, setTargetGrade] = useState(80);
  const [requiredGrade, setRequiredGrade] = useState("76.7");
  const [cardIndex, setCardIndex] = useState(0);
  const [cardFlipped, setCardFlipped] = useState(false);

  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([getTodayTodos(), getFocusAnalytics(), getActiveFocus()]).then((results) => {
      if (cancelled) return;
      const todoResult = results[0];
      const analyticsResult = results[1];
      const focusResult = results[2];
      if (todoResult.status === "fulfilled" && todoResult.value.items.length) {
        setTodos(todoResult.value.items);
        setSelectedTodo(todoResult.value.items[0]);
      } else {
        setSyncLabel("Demo data · API offline");
      }
      if (analyticsResult.status === "fulfilled") setAnalytics(analyticsResult.value);
      if (focusResult.status === "fulfilled" && focusResult.value.focus) {
        setFocus(focusResult.value.focus);
        setTimerSeconds(Math.max(0, 25 * 60 - focusResult.value.focus.duration_seconds));
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!focus || focus.status !== "running") return;
    const interval = window.setInterval(() => {
      setTimerSeconds((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [focus]);

  const deadlines = useMemo(() => todos.filter((item) => item.kind === "deadline"), [todos]);
  const schedule = useMemo(() => todos.filter((item) => item.kind === "schedule"), [todos]);
  const currentCard = flashcards[cardIndex];
  const weeklyHours = (analytics.total_seconds / 3600).toFixed(1);

  async function handleFocus() {
    try {
      if (!focus) {
        const next = await startFocus({
          course_id: selectedTodo.course_id,
          assignment_id: selectedTodo.assignment_id,
        });
        setFocus(next);
        return;
      }
      const action = focus.status === "running" ? "pause" : "resume";
      const next = await mutateFocus(focus.id, action);
      setFocus(next);
    } catch {
      setFocus((current) =>
        current?.status === "running"
          ? { ...current, status: "paused" }
          : { id: -1, status: "running", course_id: selectedTodo.course_id, assignment_id: selectedTodo.assignment_id, started_at: new Date().toISOString(), ended_at: null, duration_seconds: 0 },
      );
    }
  }

  async function handleCompleteFocus() {
    if (!focus) return;
    try {
      const next = focus.id > 0 ? await mutateFocus(focus.id, "complete") : null;
      setFocus(next ?? { ...focus, status: "completed", duration_seconds: 25 * 60 - timerSeconds });
    } catch {
      setFocus({ ...focus, status: "completed", duration_seconds: 25 * 60 - timerSeconds });
    }
  }

  async function handleGradeChange(value: number) {
    setTargetGrade(value);
    try {
      const result = await getGradeWhatIf(value);
      if (result.required_average_percent) setRequiredGrade(Number(result.required_average_percent).toFixed(1));
    } catch {
      setRequiredGrade(Math.max(0, 100 - (value - 70) * 0.78).toFixed(1));
    }
  }

  return (
    <main className="app-shell">
      <aside className="side-rail">
        <div className="brand-mark" aria-label="Academic OS">
          <GraduationCap size={22} />
        </div>
        <div className="rail-nav" aria-label="主导航">
          {["Today", "Calendar", "Library", "Progress"].map((label) => (
            <button className={`rail-button ${label === "Today" ? "rail-button-active" : ""}`} key={label} title={label}>
              {navIcon(label)}
              <span>{label}</span>
            </button>
          ))}
        </div>
        <button className="rail-button rail-help" title="帮助">
          <CircleHelp size={19} />
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="mobile-brand"><GraduationCap size={20} /> Academic OS</div>
          <div className="crumb"><span>SEMESTER 02</span><ChevronRight size={14} /><strong>Today</strong></div>
          <div className="topbar-actions">
            <span className="sync-pill"><span className="sync-dot" /> {syncLabel}</span>
            <button className="avatar" aria-label="个人资料">JZ</button>
          </div>
        </header>

        <div className="content-grid">
          <section className="today-column">
            <div className="headline-block">
              <p className="eyebrow">SATURDAY · 20 SEP 2026</p>
              <h1>Make the next<br /><em>25 minutes</em> count.</h1>
              <p className="lede">Your academic day, condensed to the few moves that matter now.</p>
            </div>

            <section className="panel task-panel">
              <div className="panel-heading">
                <div><span className="section-index">01</span><h2>Today&apos;s thread</h2></div>
                <span className="muted-count">{todos.length} moves</span>
              </div>
              <div className="task-list">
                {todos.map((todo, index) => (
                  <button className={`task-row ${selectedTodo.key === todo.key ? "task-row-selected" : ""}`} key={todo.key} onClick={() => setSelectedTodo(todo)}>
                    <span className={`task-icon task-icon-${todo.kind}`}>{kindIcon(todo.kind)}</span>
                    <span className="task-copy"><strong>{todo.title}</strong><small>{todo.kind === "deadline" ? "DDL" : todo.kind === "schedule" ? "CLASS" : "PERSONAL"} · {formatDue(todo.due_at, hydrated)}</small></span>
                    <span className="task-check">{index === 0 ? <ArrowUpRight size={16} /> : <Check size={16} />}</span>
                  </button>
                ))}
              </div>
              <button className="add-task"><span>+</span> Add a temporary task</button>
            </section>

            <section className="focus-panel">
              <div className="focus-copy">
                <p className="eyebrow eyebrow-light"><TimerReset size={14} /> DEEP WORK</p>
                <h2>{focus?.status === "running" ? "Stay with it." : "Choose your next move."}</h2>
                <p>{selectedTodo.title}</p>
                <div className="focus-controls">
                  <button className="primary-action" onClick={handleFocus}>{focus?.status === "running" ? <Pause size={16} /> : <Play size={16} />}{focus?.status === "paused" ? "Resume focus" : focus?.status === "running" ? "Pause focus" : "Start focus"}</button>
                  {focus && <button className="icon-action" title="Complete focus" onClick={handleCompleteFocus}><Check size={17} /></button>}
                </div>
              </div>
              <CircularTimer seconds={timerSeconds} running={focus?.status === "running"} />
            </section>
          </section>

          <section className="signal-column">
            <section className="panel deadline-panel">
              <div className="panel-heading"><div><span className="section-index">02</span><h2>Within reach</h2></div><AlarmClock size={19} className="panel-icon" /></div>
              <div className="deadline-stack">
                {deadlines.length ? deadlines.map((deadline) => (
                  <div className="deadline-card" key={deadline.key}>
                    <div className="deadline-stripe" />
                    <div className="deadline-meta"><span>{formatDue(deadline.due_at, hydrated)}</span><span>UNSUBMITTED</span></div>
                    <h3>{deadline.title.split(" · ").pop()}</h3>
                    <p>{deadline.title.split(" · ")[0]}</p>
                    <button onClick={() => setSelectedTodo(deadline)}>Focus this <ArrowUpRight size={14} /></button>
                  </div>
                )) : <div className="empty-state">No urgent deadlines. Keep the calm.</div>}
              </div>
            </section>

            <section className="panel rhythm-panel">
              <div className="panel-heading"><div><span className="section-index">03</span><h2>Today&apos;s rhythm</h2></div><span className="muted-count">UTC+10</span></div>
              <div className="rhythm-list">
                {schedule.length ? schedule.map((item) => (
                  <div className="rhythm-row" key={item.key}><span className="rhythm-time">{formatScheduleTime(item.due_at, hydrated)}</span><span><strong>{item.title.split(" · ").pop()}</strong><small>{item.title.split(" · ")[0]}</small></span><span className="rhythm-dot" /></div>
                )) : <div className="empty-state">No classes scheduled today.</div>}
              </div>
            </section>

            <section className="panel flashcard-panel">
              <div className="panel-heading"><div><span className="section-index">04</span><h2>One card to keep</h2></div><Sparkles size={18} className="spark-icon" /></div>
              <button className={`flashcard ${cardFlipped ? "flashcard-flipped" : ""}`} onClick={() => setCardFlipped((current) => !current)} aria-label="翻转复习卡片">
                <span className="flashcard-tag">{currentCard.tag}</span>
                <strong>{cardFlipped ? currentCard.answer : currentCard.question}</strong>
                <span className="flashcard-hint">{cardFlipped ? "answer · tap to return" : "question · tap to reveal"}</span>
              </button>
              <div className="card-pager"><button onClick={() => { setCardIndex((cardIndex + flashcards.length - 1) % flashcards.length); setCardFlipped(false); }}><ChevronRight size={15} className="flip-left" /></button><span>{cardIndex + 1} / {flashcards.length}</span><button onClick={() => { setCardIndex((cardIndex + 1) % flashcards.length); setCardFlipped(false); }}><ChevronRight size={15} /></button></div>
            </section>
          </section>

          <aside className="insight-column">
            <section className="panel study-panel">
              <div className="panel-heading"><div><span className="section-index">05</span><h2>Study pulse</h2></div><TrendingUp size={18} className="mint-icon" /></div>
              <div className="pulse-number"><strong>{weeklyHours}</strong><span>hours<br />this week</span></div>
              <div className="chart-wrap chart-wrap-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={analytics.daily}><defs><linearGradient id="pulseFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#bce7d3" stopOpacity={0.42} /><stop offset="100%" stopColor="#bce7d3" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#e5e1d7" /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "#8993a1", fontSize: 10 }} /><YAxis hide /><Tooltip cursor={{ stroke: "#ff704a", strokeDasharray: "3 3" }} formatter={(value) => [`${Math.round(Number(value) / 60)}m`, "focus"]} /><Area type="monotone" dataKey="seconds" stroke="#6cac8f" fill="url(#pulseFill)" strokeWidth={2.5} /></AreaChart></ResponsiveContainer></div>
            </section>

            <section className="panel course-panel">
              <div className="panel-heading"><div><span className="section-index">06</span><h2>By course</h2></div><BookOpen size={18} className="panel-icon" /></div>
              <div className="bar-chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={analytics.by_course} layout="vertical" margin={{ left: 5, right: 8 }}><XAxis type="number" hide /><YAxis type="category" dataKey="course" axisLine={false} tickLine={false} width={82} tick={{ fill: "#5b6574", fontSize: 10 }} /><Tooltip cursor={{ fill: "#f0ede5" }} formatter={(value) => [`${Math.round(Number(value) / 60)}m`, "focus"]} /><Bar dataKey="seconds" fill="#95a4b8" radius={[0, 3, 3, 0]} barSize={11} /></BarChart></ResponsiveContainer></div>
            </section>

            <section className="panel grade-panel">
              <div className="panel-heading"><div><span className="section-index">07</span><h2>What-if grade</h2></div><Target size={18} className="orange-icon" /></div>
              <div className="grade-target"><span>Target total</span><strong>{targetGrade}<small>/ 100</small></strong></div>
              <input aria-label="目标总评" type="range" min="50" max="95" value={targetGrade} onChange={(event) => void handleGradeChange(Number(event.target.value))} />
              <div className="grade-foot"><span>Required on remaining</span><strong>{requiredGrade}%</strong></div>
              <p className="fine-print">Based on synced assignment group weights.</p>
            </section>
          </aside>
        </div>
        <footer className="page-footer"><span><Clock3 size={14} /> Last sync · just now</span><span>Academic OS / built for the long semester</span><button><Menu size={14} /> Menu</button></footer>
      </section>
    </main>
  );
}
