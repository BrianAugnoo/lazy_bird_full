from lazy_bird.errors import ConflictError


class UniqueFieldError(ConflictError):
    """Raised when a unique field constraint is violated."""

    code = "unique_field_violation"

    def __init__(self, field_name: str, field_value: str):
        self.field_name = field_name
        self.field_value = field_value
        super().__init__(
            f"The field '{field_name}' with value '{field_value}' already exists and must be unique.",
            details={"field": field_name, "value": field_value},
        )
