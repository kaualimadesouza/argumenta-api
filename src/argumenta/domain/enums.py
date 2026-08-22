import enum


class Exam(enum.StrEnum):
    ENEM = "enem"
    FUVEST = "fuvest"


class AuthProvider(enum.StrEnum):
    GOOGLE = "google"
    EMAIL = "email"


class DevicePlatform(enum.StrEnum):
    IOS = "ios"
    ANDROID = "android"


class ContentStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ChapterKind(enum.StrEnum):
    CONFRONTO = "confronto"
    CHEFE = "chefe"


class Branch(enum.StrEnum):
    MAIN = "main"
    CONSEQUENCE = "consequence"
    RECOVERY = "recovery"


class BeatType(enum.StrEnum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    OBJECTIVE = "objective"
    HINT = "hint"


class SubmissionContext(enum.StrEnum):
    MAIN = "main"
    RECOVERY = "recovery"


class Verdict(enum.StrEnum):
    APPROVED = "approved"
    FAILED_TECHNICAL = "failed_technical"
    FAILED_PERSUASION = "failed_persuasion"


class Dimension(enum.StrEnum):
    NORMA_CULTA = "norma_culta"
    COESAO = "coesao"
    COERENCIA = "coerencia"
    REPERTORIO = "repertorio"
    PERSUASAO = "persuasao"
    PROPOSTA_INTERVENCAO = "proposta_intervencao"


class AnnotationType(enum.StrEnum):
    SPELLING = "spelling"
    ACCENTUATION = "accentuation"
    PUNCTUATION = "punctuation"
    GRAMMAR = "grammar"
    COHESION = "cohesion"
    COHERENCE = "coherence"
    REPERTOIRE_ALERT = "repertoire_alert"
    REPERTOIRE_PRAISE = "repertoire_praise"
    PERSUASION = "persuasion"


class Severity(enum.StrEnum):
    ERROR = "error"
    WARNING = "warning"
    PRAISE = "praise"


class ReactionBeat(enum.StrEnum):
    REBUTTAL = "rebuttal"
    CONVINCED = "convinced"
    CONSEQUENCE_INTRO = "consequence_intro"
    RECOVERY_PROMPT = "recovery_prompt"


class ChapterStatus(enum.StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    DRAFTING = "drafting"
    IN_CONSEQUENCE = "in_consequence"
    IN_RECOVERY = "in_recovery"
    PASSED = "passed"


class TelemetryEventType(enum.StrEnum):
    """Stored as text (DER), validated here: an unknown type is a client bug,
    not a new column. Each value has a payload type in domain.telemetry."""

    PASTE = "paste"
    TYPING_STATS = "typing_stats"
    SCREEN_VIEW = "screen_view"
