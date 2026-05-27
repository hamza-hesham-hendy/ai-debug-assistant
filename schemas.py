from pydantic import BaseModel


class RegisterFormData(BaseModel):
    username: str
    email: str
    password: str


class LoginFormData(BaseModel):
    username: str
    password: str
