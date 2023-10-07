from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import List
from sqlalchemy import String, Integer, Float, ForeignKey
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import smtplib
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)
gravatar = Gravatar(
    app, size=100, rating="g", default="retro", force_default=False, force_lower=False, use_ssl=False, base_url=None
)

# Configure Flask-Login ✅
login_manager = LoginManager()
login_manager.init_app(app)


# creating a user_loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy()
db.init_app(app)


# Create a User table for all your registered users. ✅
class User(UserMixin, db.Model):
    __tablename__ = "users"

    # id: Mapped[Integer] = mapped_column(Integer, primary_key=True)
    id = db.Column(db.Integer, primary_key=True)
    # name: Mapped[String] = mapped_column(String(500))
    name = db.Column(db.String(500))
    # email: Mapped[String] = mapped_column(String(100), unique=True)
    email = db.Column(db.String(100), unique=True)
    # password: Mapped[String] = mapped_column(String(100))
    password = db.Column(db.String(100))

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    # children: Mapped[List["BlogPost"]] = relationship(back_populates="parent")

    # *******Add parent relationship*******#
    # "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the table-name of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "posts" refers to the posts property  in the User class.
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    # author = db.Column(db.String(250), nullable=False) # no longer needed because derived from the relationship
    img_url = db.Column(db.String(250), nullable=False)

    # author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # parent: Mapped["User"] = relationship(back_populates="children")

    # ***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # ******* Add child relationship ******* #
    # "users.id" The users refer to the tablename of the Users class.
    # "comments" refers to the comments property in the User class.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")

    # ***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


# CONFIGURE TABLES
with app.app_context():
    db.create_all()


# Use Werkzeug to hash the user's password when creating a new user. ✅
@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():

        user_exist = db.session.execute(db.select(User).where(User.email == register_form.email.data)).scalar()
        if user_exist:
            # User already exists
            flash("You've already signed up with this email, Log in instead")
            return redirect(url_for("login"))

        hashed_and_salted_passwd = generate_password_hash(password=request.form.get("password"),
                                                          method="pbkdf2:sha256",
                                                          salt_length=8
                                                          )
        new_user = User(
            name=request.form.get("name"),
            email=request.form.get("email"),
            password=hashed_and_salted_passwd
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=register_form)


# Retrieve a user from the database based on their email. ✅
@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again")
            return redirect(url_for("login"))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash("Password incorrect, please try again")
            return redirect(url_for("login"))
        # all credentials check out/are correct...
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    # user_id = request.args.get("user")   is_admin=True if user_id == "1" else False
    user = db.session.execute(db.select(User)).scalars()
    return render_template("index.html", all_posts=posts, user=user)


# Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if current_user.is_authenticated:
            comment = comment_form.comment.data
            # new_comment = Comment(
            #     text=comment,
            #     author_id=current_user.id,
            #     post_id=requested_post.id
            # )
            # RIGHT WAY
            new_comment = Comment(
                text=comment_form.comment.data,
                comment_author=current_user,
                parent_post=requested_post
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("Log in first to be able to comment")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=comment_form)


def admin_only(function):
    @wraps(function)
    # @login_required  # prevent -> AttributeError: 'AnonymousUserMixin' object has no attribute 'id'
    def decorated_function(*args, **kwargs):
        # If id is not 1, then return abort with 403 error
        # if current_user.id != 1:  # not args[0]
        if (current_user.is_authenticated and current_user.id != 1) or (not current_user.is_authenticated):
            return abort(403)
        # Otherwise continue with the route function
        return function(*args, **kwargs)

    return decorated_function


# Use a decorator so only an admin user can create a new post ✅
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# Use a decorator so only an admin user can edit a post ✅
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# Use a decorator so only an admin user can delete a post ✅
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


MAIL_ADDRESS = os.environ.get("EMAIL_KEY")
MAIL_APP_PW = os.environ.get("PASSWORD_KEY")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.form
        send_email(data["name"], data["email"], data["phone"], data["message"])
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


def send_email(name, email, phone, message):
    email_message = f"Subject:New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage:{message}"
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(MAIL_ADDRESS, MAIL_APP_PW)
        connection.sendmail(from_addr=MAIL_ADDRESS, to_addrs=MAIL_ADDRESS, msg=email_message)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
