from takumi.validation.errors import MultipleErrorsError, ValidationError


class Validator:
    def validate(self, *args, **kwargs):
        """Validate a single requirement

        Should raise an instance of ValidationError if invalid
        """
        raise NotImplementedError


class ComposedValidator:
    def __init__(self, validators):
        self.validators = validators

    def validate(self, *args, **kwargs):
        self.errors = []

        for validator in self.validators:
            try:
                validator.validate(*args, **kwargs)
            except ValidationError as exc:
                self.errors.append(exc)

        if any(self.errors):
            raise MultipleErrorsError(self.errors)
