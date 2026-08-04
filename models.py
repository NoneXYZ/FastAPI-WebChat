from pydantic import BaseModel, field_validator
import re

# What the user sends from the registration form
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PASSWORD_REGEX = re.compile(r"^.{8,64}$")

class UserCreate(BaseModel):
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

class UserLogin(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

class MessageCreate(BaseModel):
    content: str