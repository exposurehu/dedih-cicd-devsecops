from pydantic import BaseModel, Field


class Greeting(BaseModel):
    # The name is between 1 and 50 characters. This validation is the defense
    # in depth layer: the backend does not trust the frontend, it checks the
    # incoming data again.
    name: str = Field(min_length=1, max_length=50)
