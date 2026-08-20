from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import VerifyMismatchError


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = _Argon2()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False
        except Exception:
            # malformed hash (e.g. legacy or corrupted row) must fail closed
            return False
