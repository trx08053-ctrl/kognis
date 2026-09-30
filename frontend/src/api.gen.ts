// auto-generated: scripts/gen_api_types.py из OpenAPI бэкенда — не редактировать
export interface components {
  schemas: {
    AcceptIn: {
      "template": string;
    };
    AchievementOut: {
      "code": string;
      "title": string;
      "description": string;
      "earned_on": string;
    };
    AnalysisOut: {
      "id": number;
      "parent_id": number | null;
      "direction": string;
      "start": string;
      "end": string;
      "status": string;
      "summary": string | null;
      "patterns": (components["schemas"]["PatternOut"])[];
      "questions": (string)[];
      "quest_ideas": (string)[];
      "changes": (string)[];
      "answers": (string)[];
      "created_at": string | null;
      "help"?: components["schemas"]["HelpOut"] | null;
    };
    AnalyzeIn: {
      "direction": string;
      "start": string;
      "end": string;
      "consent"?: boolean;
    };
    AnswersIn: {
      "answers": (string)[];
      "consent"?: boolean;
    };
    ContactOut: {
      "name": string;
      "phone": string;
      "note": string;
    };
    Credentials: {
      "email": string;
      "password": string;
    };
    DayReviewIn: {
      "wellbeing": number;
      "mood": number;
      "reflection"?: string;
    };
    DayReviewOut: {
      "id": number;
      "date": string;
      "wellbeing": number;
      "mood": number;
      "reflection": string;
      "help"?: components["schemas"]["HelpOut"] | null;
    };
    DirectionOut: {
      "code": string;
      "title": string;
    };
    EntryIn: {
      "text"?: string;
      "tags"?: (string)[];
      "emotions"?: (string)[];
      "date"?: string | null;
      "protection"?: "plain" | "locked" | "private";
      "lock_password"?: string | null;
      "cipher"?: Record<string, unknown> | null;
    };
    EntryOut: {
      "id": number;
      "date": string;
      "text": string;
      "tags": (string)[];
      "emotions": (string)[];
      "protection": string;
      "crisis"?: boolean;
      "cipher"?: Record<string, unknown> | null;
      "help"?: components["schemas"]["HelpOut"] | null;
    };
    FromAnalysisIn: {
      "analysis_id": number;
      "idea": number;
    };
    HTTPValidationError: {
      "detail"?: (components["schemas"]["ValidationError"])[];
    };
    HelpOut: {
      "message": string;
      "contacts": (components["schemas"]["ContactOut"])[];
    };
    LabelsOut: {
      "tags": (string)[];
      "emotions": (string)[];
    };
    LockPassword: {
      "password": string;
    };
    MemoryOut: {
      "digest": string;
      "updated_at": string | null;
    };
    MoodOut: {
      "points": (components["schemas"]["MoodPointOut"])[];
      "average_mood": number | null;
      "average_wellbeing": number | null;
      "trend": string;
    };
    MoodPointOut: {
      "date": string;
      "mood": number;
      "wellbeing": number;
    };
    PatternOut: {
      "title": string;
      "description": string;
      "entry_ids": (number)[];
      "quotes": (string)[];
    };
    PeriodOut: {
      "start": string;
      "end": string;
      "active": boolean;
      "truncated": boolean;
      "last_analysis_id": number | null;
    };
    ProgressOut: {
      "xp": number;
      "level": number;
      "level_start_xp": number;
      "next_level_xp": number;
      "streak": number;
      "achievements": (components["schemas"]["AchievementOut"])[];
    };
    QuestOut: {
      "id": number;
      "source": string;
      "template_code": string | null;
      "kind": string;
      "title": string;
      "description": string;
      "created_on": string;
      "completed_on": string | null;
      "steps": (components["schemas"]["QuestStepOut"])[];
    };
    QuestStepOut: {
      "idx": number;
      "title": string;
      "done_on": string | null;
    };
    QuestTemplateOut: {
      "code": string;
      "title": string;
      "description": string;
      "direction": string;
      "kind": string;
      "steps": (string)[];
    };
    QuizAnswersIn: {
      "answers": (string)[];
    };
    QuizAnswersOut: {
      "date": string;
      "answers": (string)[];
    };
    QuizOut: {
      "code": string;
      "title": string;
      "questions": (string)[];
      "done_today": boolean;
    };
    QuizResultOut: {
      "xp": number;
      "saved": components["schemas"]["QuizAnswersOut"];
      "help"?: components["schemas"]["HelpOut"] | null;
    };
    RegisterIn: {
      "email": string;
      "password": string;
      "timezone"?: string | null;
    };
    SettingsIn: {
      "advanced"?: boolean | null;
      "timezone"?: string | null;
      "locale"?: string | null;
    };
    StepDoneOut: {
      "quest": components["schemas"]["QuestOut"];
      "xp": number;
    };
    UserOut: {
      "id": number;
      "email": string;
      "advanced"?: boolean;
      "timezone"?: string;
      "locale"?: string;
      "today": string;
    };
    ValidationError: {
      "loc": (string | number)[];
      "msg": string;
      "type": string;
      "input"?: unknown;
      "ctx"?: Record<string, unknown>;
    };
  };
}
