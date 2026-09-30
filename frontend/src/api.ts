// Клиент HTTP API бэкенда (/api/*). Типы ответов и запросов — из схемы OpenAPI бэкенда (api.gen.ts,
// `just api-types`); здесь они только сужаются (Refine): переименование поля в схеме ломает tsc.
// Сессия — httpOnly cookie, её ставит и читает браузер; изменяющие запросы — только JSON (CSRF, ADR 0003).

import type { components } from "./api.gen";
import { type EntryQuery, type Page, pageUrl, toPage } from "./pagination";
import type { Envelope } from "./privateCrypto";

type Schemas = components["schemas"];

// сужение типа схемы: ключи и типы R обязаны существовать в T (иначе ошибка компиляции)
type Refine<T, R extends { [K in keyof R]: K extends keyof T ? T[K] : never }> = Omit<T, keyof R> &
  R;

// поля со значением по умолчанию сервер отдаёт всегда, хотя в схеме они необязательны
export type User = Refine<Schemas["UserOut"], { advanced: boolean; timezone: string }>;
export type HelpContact = Schemas["ContactOut"];
export type HelpBlock = Schemas["HelpOut"];
export type Entry = Refine<Schemas["EntryOut"], { crisis: boolean; cipher?: Envelope | null }>;
export type NewEntry = Refine<Schemas["EntryIn"], { cipher?: Envelope }>;

// Ошибка API: сервер отдаёт код и параметры, текст по коду берёт интерфейс (docs/I18N.md, errors.ts)
export class ApiError extends Error {
  constructor(
    readonly code: string | null,
    readonly status: number,
    readonly params: Record<string, string | number> = {},
  ) {
    super(code ?? `http ${status}`);
  }
}

// detail списком — ошибка формы от валидатора (пустое или нечисловое поле)
const VALIDATION_CODE = "request.validation";

function errorFrom(status: number, detail: unknown): ApiError {
  if (Array.isArray(detail)) return new ApiError(VALIDATION_CODE, status);
  if (typeof detail === "object" && detail !== null && "code" in detail) {
    const { code, params } = detail as { code: unknown; params?: Record<string, string | number> };
    if (typeof code === "string") return new ApiError(code, status, params ?? {});
  }
  return new ApiError(null, status);
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw errorFrom(response.status, body.detail);
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
export const register = (
  email: string,
  password: string,
  timezone: string | null = null,
): Promise<User> => post<User>("/api/auth/register", { email, password, timezone });
export const login = (email: string, password: string): Promise<User> =>
  post<User>("/api/auth/login", { email, password });
export const saveSettings = (settings: { advanced?: boolean; timezone?: string }): Promise<User> =>
  fetch("/api/me/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  }).then((r) => parse<User>(r));
export const logout = (): Promise<void> => post<void>("/api/auth/logout");

async function getPage<T>(url: string): Promise<Page<T>> {
  const response = await fetch(url);
  return toPage(await parse<T[]>(response), response);
}

export const listEntries = (query: EntryQuery = {}): Promise<Page<Entry>> =>
  getPage<Entry>(pageUrl("/api/entries", query));
export type EntryLabels = Schemas["LabelsOut"];
export const getEntryLabels = (): Promise<EntryLabels> =>
  fetch("/api/entries/labels").then((r) => parse<EntryLabels>(r));
export const createEntry = (entry: NewEntry): Promise<Entry> => post<Entry>("/api/entries", entry);

export type DayReview = Schemas["DayReviewOut"];
export type DayReviewInput = Schemas["DayReviewIn"];
export type Achievement = Schemas["AchievementOut"];
export type Progress = Schemas["ProgressOut"];

export const getProgress = (): Promise<Progress> =>
  fetch("/api/progress").then((r) => parse<Progress>(r));

export const listDayReviews = (
  query: { limit?: number; cursor?: string | null } = {},
): Promise<Page<DayReview>> => getPage<DayReview>(pageUrl("/api/day-reviews", query));

export type Direction = Schemas["DirectionOut"];
export type Pattern = Schemas["PatternOut"];
export type Analysis = Refine<Schemas["AnalysisOut"], { status: "done" | "crisis" }>;
export type MoodPoint = Schemas["MoodPointOut"];
export type MoodDynamics = Refine<
  Schemas["MoodOut"],
  { trend: "up" | "down" | "flat" | "unknown" }
>;
export type AnalysisRequest = Schemas["AnalyzeIn"];

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

export type QuestStep = Schemas["QuestStepOut"];
export type Quest = Refine<
  Schemas["QuestOut"],
  { source: "library" | "analysis"; kind: "quest" | "challenge" }
>;
export type QuestTemplate = Refine<Schemas["QuestTemplateOut"], { kind: "quest" | "challenge" }>;
export type StepDone = Refine<Schemas["StepDoneOut"], { quest: Quest }>;
export type Quiz = Schemas["QuizOut"];
export type QuizResult = Schemas["QuizResultOut"];

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
