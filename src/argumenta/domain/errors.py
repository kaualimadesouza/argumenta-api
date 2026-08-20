class DomainError(Exception):
    """Base for every business-rule violation; presentation maps these to HTTP."""


class EmailAlreadyRegisteredError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class TermsNotAcceptedError(DomainError):
    pass


class GoogleSignInFailedError(DomainError):
    pass


class ExamTargetAlreadyExistsError(DomainError):
    pass


class ExamTargetNotFoundError(DomainError):
    pass


class TooManyAttemptsError(DomainError):
    pass


class ChapterNotFoundError(DomainError):
    pass


class ChapterLockedError(DomainError):
    pass


class LlmBudgetExceededError(DomainError):
    pass


class EvaluationFailedError(DomainError):
    pass


class ChapterNotWritableError(DomainError):
    pass


class WordCountOutOfRangeError(DomainError):
    pass


class DailyLimitReachedError(DomainError):
    pass
