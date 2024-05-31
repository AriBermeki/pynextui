from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from pynextui_ import (
    TextField,
    Form,
    TextField,
    FormActions,
    SubmitButton,
    AdminApp,
    MenuItem,
    Checkbox,
    DatePicker
)
from pathlib import Path


class UserCreation(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: EmailStr
    phone: int
    password: str
    confirm_password: str
    secret_key: Optional[str] = None
    is_active: bool = False
    is_admin: bool = False
    is_superuser: bool = False
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    otp_creation_time: datetime
    otp: str


logo = Path(__file__).parent / "logo.png" 

app = AdminApp(app_favicon=logo)

def on_submit(form_data):
    user = UserCreation(**form_data)
    print(user.model_dump_json(indent=2))

@app.page('/', 'form')
def form_page():
    return [
        Form(on_submit=on_submit, content=[
            TextField('First Name', 'first_name'),
            TextField('Last Name', 'last_name'),
            TextField('Username', 'username'),
            TextField('Email', 'email'),
            TextField('Phone', 'phone'),
            TextField('Password', 'password'),
            TextField('Confirm Password', 'confirm_password'),
            TextField('OTP', 'otp'),
            DatePicker('OTP Creation Time', 'otp_creation_time'),
            DatePicker('Created At', 'created_at'),
            DatePicker('Updated At', 'updated_at'),
            Checkbox('Is Active', 'is_active'),
            Checkbox('Is Admin', 'is_admin'),
            Checkbox('Is Superuser', 'is_superuser'),
            Checkbox('Is Verified', 'is_verified'),
            FormActions(content=[
                SubmitButton('Submit')
            ])
        ])
    ]

@app.page('/detail', 'detail')
def detail_page():
    return [
    ]

app.set_menu(
    [
        MenuItem('User Creation System', '/', icon="dashboard"),
        MenuItem('Detail Page', '/detail', icon="info-circle")
    ]
)

