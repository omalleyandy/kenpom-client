from __future__ import annotations


class KenPomError(RuntimeError):
    pass


class KenPomAuthError(KenPomError):
    pass


class KenPomRateLimitError(KenPomError):
    pass


class KenPomServerError(KenPomError):
    pass


class KenPomClientError(KenPomError):
    pass
