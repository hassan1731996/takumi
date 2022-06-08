class GraphQLException(Exception):
    def __init__(self, message, errors=None, error_code=None):
        super().__init__(message)
        self.errors = errors
        self.error_code = error_code


class FieldException(GraphQLException):
    pass


class MutationException(GraphQLException):
    pass


class QueryException(GraphQLException):
    pass


class PreconditionFailedException(GraphQLException):
    pass


class ValidationException(GraphQLException):
    pass


class InvalidUrlException(ValidationException):
    pass
