from lazy_bird.crud.error import UniqueFieldError


def test_unique_field_error_exposes_field_information():
    error = UniqueFieldError(field_name="name", field_value="HuggingFace")

    assert error.field_name == "name"
    assert error.field_value == "HuggingFace"
    assert "name" in str(error)
    assert "HuggingFace" in str(error)
