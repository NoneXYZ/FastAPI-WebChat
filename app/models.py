from pydantic import BaseModel, Field, field_validator
import re

# What the user sends from the registration form
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PASSWORD_REGEX = re.compile(r"^.{8,64}$")

class UserCredentials(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        # Strip whitespace AND force lowercase
        clean_value = value.strip().lower()
        
        if not USERNAME_REGEX.match(clean_value):
            raise ValueError(
                "Username must be 3-20 characters long and can only contain letters, numbers, underscores, and hyphens."
            )
        return clean_value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not PASSWORD_REGEX.match(value):
            raise ValueError(
                "Password must be 8-64 characters long."
            )
        return value

# --- IMPROVED MODEL ---
class MessageCreate(BaseModel):
    # Field constraints enforce length validation before the code hits the database
    content: str = Field(
        ..., 
        min_length=1, 
        max_length=2000, 
        description="The text content of the message. Cannot be empty or purely whitespace."
    )
    # Optional client-side ID to prevent double-posting / duplicate delivery
    client_msg_id: str | None = Field(
        default=None, 
        description="Optional client-generated UUID to ensure message idempotency."
    )

    # Automatically strips leading/trailing whitespaces during validation
    @property
    def clean_content(self) -> str:
        return self.content.strip()