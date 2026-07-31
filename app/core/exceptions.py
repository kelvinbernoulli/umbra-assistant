class UmbraError(Exception):
    pass


class NotFoundError(UmbraError):
    pass


class ValidationError(UmbraError):
    pass
