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
    ArchiveEntryOut: {
      "id": number;
      "date": string;
      "ago": string;
      "text": string;
      "tags": (string)[];
      "emotions": (string)[];
    };
    CategoryOut: {
      "category": string;
      "value": number;
      "next_target": number | null;
      "levels": (components["schemas"]["LevelOut"])[];
    };
    CompanionIn: {
      "appearance": string;
      "name": string;
      "address": string;
    };
    CompanionOut: {
      "chosen": boolean;
      "appearance": string | null;
      "name": string | null;
      "address": string | null;
      "stage": number;
      "days_total": number;
      "days_to_next": number | null;
      "resting": boolean;
      "line": components["schemas"]["LineOut"] | null;
      "postcard": components["schemas"]["PostcardOut"] | null;
      "mentors": (components["schemas"]["MentorOut"])[];
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
    DailyChooseIn: {
      "code": string;
    };
    DailyOut: {
      "options": (string)[];
      "picked": string | null;
      "done": boolean;
      "weekly": string | null;
    };
    DayReviewIn: {
      "wellbeing": number;
      "mood": number;
      "reflection"?: string;
      "marks"?: ("step" | "good" | "reframe" | "insight")[];
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
      "marks"?: ("step" | "good" | "reframe" | "insight")[];
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
    HiddenOut: {
      "code": string;
      "earned_on": string | null;
    };
    LabelsOut: {
      "tags": (string)[];
      "emotions": (string)[];
    };
    LevelOut: {
      "code": string;
      "level": number;
      "target": number;
      "earned_on": string | null;
    };
    LineOut: {
      "hero": string;
      "situation": string;
    };
    LockPassword: {
      "password": string;
    };
    MemoryOut: {
      "digest": string;
      "updated_at": string | null;
    };
    MentorOut: {
      "code": string;
      "direction": string;
      "unlocked": boolean;
    };
    MoodDayOut: {
      "date": string;
      "mood": number;
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
    MoodYearOut: {
      "days": (components["schemas"]["MoodDayOut"])[];
    };
    OnThisDayOut: {
      "entries": (components["schemas"]["ArchiveEntryOut"])[];
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
    PostcardOut: {
      "code": string;
      "for_day": string;
    };
    ProgressOut: {
      "xp": number;
      "level": number;
      "level_start_xp": number;
      "next_level_xp": number;
      "streak": number;
      "best_streak": number;
      "freezes": number;
      "days_30": number;
      "days_total": number;
      "weekly_goal": number;
      "week_days": number;
      "weekend_days": (number)[];
      "recovery": components["schemas"]["RecoveryOfferOut"] | null;
      "achievements": (components["schemas"]["AchievementOut"])[];
      "categories": (components["schemas"]["CategoryOut"])[];
      "hidden": (components["schemas"]["HiddenOut"])[];
    };
    PurchaseIn: {
      "item": string;
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
    RecoveryIn: {
      "note": string;
    };
    RecoveryOfferOut: {
      "streak_before": number;
      "broken_on": string;
      "expires_on": string;
    };
    RegisterIn: {
      "email": string;
      "password": string;
      "timezone"?: string | null;
    };
    ShopPositionOut: {
      "code": string;
      "kind": string;
      "price": number;
      "owned": boolean;
    };
    SparksOut: {
      "balance": number;
      "freezes": number;
      "catalog": (components["schemas"]["ShopPositionOut"])[];
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
    kognis__web___progress__SettingsIn: {
      "weekend_days": (number)[];
      "weekly_goal": number;
    };
    kognis__web___settings__SettingsIn: {
      "advanced"?: boolean | null;
      "timezone"?: string | null;
      "locale"?: string | null;
    };
  };
}
