from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class LoginForm(FlaskForm):
    username = StringField("帳號", validators=[DataRequired()])
    password = PasswordField("密碼", validators=[DataRequired()])
    submit = SubmitField("登入")


class ReviewDecisionForm(FlaskForm):
    reviewer_name = StringField("審核人員", validators=[DataRequired()])
    review_note = TextAreaField("審核備註", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("送出")


class UserForm(FlaskForm):
    username = StringField("帳號", validators=[DataRequired(), Length(min=3, max=50)])
    full_name = StringField("姓名", validators=[DataRequired(), Length(min=2, max=120)])
    password = PasswordField("密碼", validators=[DataRequired(), Length(min=6, max=120)])
    role = StringField("角色", validators=[Optional()])
    submit = SubmitField("建立帳號")
