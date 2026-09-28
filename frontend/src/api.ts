// Клиент HTTP API бэкенда (/api/*). Типы повторяют схемы FastAPI (UserOut, EntryOut).
// Сессия — httpOnly cookie, её ставит и читает браузер; изменяющие запросы — только JSON (CSRF, ADR 0003).

export interface User {
  id: number;
  email: string;
}

export interface HelpContact {
  name: string;
  phone: string;
  note: string;
}

export interface HelpBlock {
  message: string;
  contacts: HelpContact[];
}

export interface Entry {
  id: number;
  date: string;
  text: string;
  tags: string[];
  emotions: string[];
  protection: string;
  crisis: boolean;
  help: HelpBlock | null;
}

export interface NewEntry {
  text: string;
  tags: string[];
  emotions: string[];
  protection?: "plain" | "locked";
  lock_password?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    // detail списком — ошибка формы от валидатора (пустое или нечисловое поле)
    let detail = `ошибка ${response.status}`;
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = "Проверьте поля формы: значения указаны неверно";
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function post<T>(url: string, body: unknown = {}): Promise<T> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((response) => parse<T>(response));
}

export const getMe = (): Promise<User> => fetch("/api/me").then((r) => parse<User>(r));
export const register = (email: string, password: string): Promise<User> =>
  post<User>("/api/auth/register", { email, password });
export const login = (email: string, password: string): Promise<User> =>
  post<User>("/api/auth/login", { email, password });
export const logout = (): Promise<void> => post<void>("/api/auth/logout");
export const listEntries = (): Promise<Entry[]> =>
  fetch("/api/entries").then((r) => parse<Entry[]>(r));
export const createEntry = (entry: NewEntry): Promise<Entry> => post<Entry>("/api/entries", entry);

export interface DayReview {
  id: number;
  date: string;
  wellbeing: number;
  mood: number;
  reflection: string;
  help: HelpBlock | null;
}

export interface DayReviewInput {
  wellbeing: number;
  mood: number;
  reflection: string;
}

export interface Achievement {
  code: string;
  title: string;
  description: string;
  earned_on: string;
}

export interface Progress {
  xp: number;
  level: number;
  level_start_xp: number;
  next_level_xp: number;
  streak: number;
  achievements: Achievement[];
}

export const getProgress = (): Promise<Progress> =>
  fetch("/api/progress").then((r) => parse<Progress>(r));

export const listDayReviews = (): Promise<DayReview[]> =>
  fetch("/api/day-reviews").then((r) => parse<DayReview[]>(r));
export interface Direction {
  code: string;
  title: string;
}

export interface Pattern {
  title: string;
  description: string;
  entry_ids: number[];
  quotes: string[];
}

export interface Analysis {
  id: number;
  parent_id: number | null;
  direction: string;
  start: string;
  end: string;
  status: "done" | "crisis";
  summary: string | null;
  patterns: Pattern[];
  questions: string[];
  quest_ideas: string[];
  answers: string[];
  help: HelpBlock | null;
}

export interface MoodPoint {
  date: string;
  mood: number;
  wellbeing: number;
}

export interface MoodDynamics {
  points: MoodPoint[];
  average_mood: number | null;
  average_wellbeing: number | null;
  trend: "up" | "down" | "flat" | "unknown";
}

export interface AnalysisRequest {
  direction: string;
  start: string;
  end: string;
  consent: boolean;
}

export const listDirections = (): Promise<Direction[]> =>
  fetch("/api/analyses/directions").then((r) => parse<Direction[]>(r));
export const getMood = (start: string, end: string): Promise<MoodDynamics> =>
  fetch(`/api/analyses/mood?start=${start}&end=${end}`).then((r) => parse<MoodDynamics>(r));
export const listAnalyses = (): Promise<Analysis[]> =>
  fetch("/api/analyses").then((r) => parse<Analysis[]>(r));
export const runAnalysis = (request: AnalysisRequest): Promise<Analysis> =>
  post<Analysis>("/api/analyses", request);
export const answerAnalysis = (
  id: number,
  answers: string[],
  consent: boolean,
): Promise<Analysis> => post<Analysis>(`/api/analyses/${id}/answers`, { answers, consent });

export const saveDayReview = (date: string, review: DayReviewInput): Promise<DayReview> =>
  fetch(`/api/day-reviews/${date}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(review),
  }).then((r) => parse<DayReview>(r));

export interface QuestStep {
  idx: number;
  title: string;
  done_on: string | null;
}

export interface Quest {
  id: number;
  source: "library" | "analysis";
  template_code: string | null;
  kind: "quest" | "challenge";
  title: string;
  description: string;
  created_on: string;
  completed_on: string | null;
  steps: QuestStep[];
}

export interface QuestTemplate {
  code: string;
  title: string;
  description: string;
  direction: string;
  kind: "quest" | "challenge";
  steps: string[];
}

export interface StepDone {
  quest: Quest;
  xp: number;
}

export interface Quiz {
  code: string;
  title: string;
  questions: string[];
  done_today: boolean;
}

export interface QuizResult {
  xp: number;
  saved: { date: string; answers: string[] };
  help: HelpBlock | null;
}

export const listQuestLibrary = (): Promise<QuestTemplate[]> =>
  fetch("/api/quests/library").then((r) => parse<QuestTemplate[]>(r));
export const listQuests = (): Promise<Quest[]> =>
  fetch("/api/quests").then((r) => parse<Quest[]>(r));
export const acceptQuest = (template: string): Promise<Quest> =>
  post<Quest>("/api/quests", { template });
export const acceptQuestFromAnalysis = (analysisId: number, idea: number): Promise<Quest> =>
  post<Quest>("/api/quests/from-analysis", { analysis_id: analysisId, idea });
export const completeQuestStep = (questId: number, idx: number): Promise<StepDone> =>
  post<StepDone>(`/api/quests/${questId}/steps/${idx}/done`);
export const listQuizzes = (): Promise<Quiz[]> =>
  fetch("/api/quizzes").then((r) => parse<Quiz[]>(r));
export const submitQuiz = (code: string, answers: string[]): Promise<QuizResult> =>
  post<QuizResult>(`/api/quizzes/${code}/answers`, { answers });

export const openEntry = (id: number, password: string): Promise<Entry> =>
  post<Entry>(`/api/entries/${id}/open`, { password });
