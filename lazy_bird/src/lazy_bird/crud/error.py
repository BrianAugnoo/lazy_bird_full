class UniqueFieldError(Exception):
    """Raised when a unique field constraint is violated."""

    def __init__(self, field_name: str, field_value: str):
        self.field_name = field_name
        self.field_value = field_value
        super().__init__(f"the field '{field_name}' with value '{field_value}'already exists and must be unique.")