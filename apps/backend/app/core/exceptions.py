from fastapi import HTTPException, status


class AppError(Exception):
    def __init__(self, message: str, code: str = "app_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def not_found(message: str = "Не найдено") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def forbidden(message: str = "Недостаточно прав") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)

