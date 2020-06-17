import os
import requests
import json

from flask import Flask, session,render_template,request,redirect,url_for,abort
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from pprint import pprint

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

search=''
#Redirect to index.html
@app.route("/")
def index():
    return render_template("login.html")

#Validating form data and entering into database    
@app.route("/register", methods=["POST","GET"])
def register():
    if request.method == "POST":
            name=request.form["name"]
            age=request.form["age"]
            email=request.form["email"]
            username=request.form["username"]
            password=request.form["password"]
            error=None
            if not username: 
                return render_template("index.html",error="Username is required.")
            elif not password:
                return render_template("index.html",error="Password is required.")
            elif db.execute("SELECT email FROM users WHERE username = :username",{"username":username}).fetchone() is not None:
                return render_template("index.html",error = "User is already registered.")
            if error is None:
                db.execute("INSERT INTO USERS(name,age,username,email,password) VALUES(:name,:age,:username,:email,:password)",{"name":name,"age":age,"username":username,"email":email,"password":generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)})                
                db.commit()
                return render_template("search.html",message="Welcome to BOOKARAZZI")
    else:
        return render_template("index.html")

#Login, if user already exists
#Otherwise, redirect to login.html
@app.route("/login", methods=["POST","GET"])
def login():
    if request.method =="POST":
        username=request.form["username"]
        entered_password=request.form["InputPassword"]
        pwhash=db.execute("SELECT * FROM USERS WHERE username=:username",{"username":username}).fetchone()
        if pwhash is not None:
            if check_password_hash(pwhash['password'],entered_password):
                session['username']=username
                return render_template("search.html")
            else:
                return render_template("login.html",error="Invalid username or password1")
        else:
            return render_template("login.html",error="Invalid username or password")
    else:  
            return render_template("login.html")

#Redirect to log_out page
@app.route("/log_out")
def log_out():
    if 'username' in session:
        session.pop('username',None)
        return render_template("log_out.html")
    else:
        return render_template("login.html",error="User already logged out.")

#Search for a book in the database and display results
@app.route("/search", methods=["POST","GET"])
def search():
#check if user is logged in
    global search
    if 'username' in session:
        if request.method=="POST":
            if (request.form.get('search_query')):
                search=request.form.get('search_query').lower()
            if (request.args.get('search_query')):
                search=request.form.get('search_query').lower()
            search1="%"+search+"%"
            results=db.execute("SELECT * FROM BOOKS WHERE lower(title) LIKE lower(:search) OR lower(author) LIKE lower(:search) or isbn LIKE :search",{"search":search1}).fetchall()
            if not results:
                return render_template("search.html",error="Ooops! No search result found.")
            return render_template("result.html",results=results)
        else:
            return render_template("search.html")
    else:
        return render_template("login.html",error="Sorry!You need to login first.")

#Search for a specific book
@app.route("/books/<string:book_id>",methods=["POST","GET"])
def books(book_id):
    if 'username' in session:
        username=session["username"]
        res=db.execute("SELECT * FROM BOOKS WHERE title LIKE :book_id",{"book_id":book_id}).fetchone()
        book_isbn=res.isbn
        r=db.execute("SELECT * from REVIEWS NATURAL JOIN BOOKS WHERE title LIKE :book_id",{"book_id":book_id,}).fetchall()
        response=requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "tbXVzxEr1fASz9erp54tw", "isbns": book_isbn})
        content=response.json()['books'][0]
        
        if res and r:
            return render_template("book.html",res=res,r=r,content=content)
        elif res:
            return render_template("book.html",res=res,content=content)
        else:
            return render_template("search.html",error="Search for a valid book.")
    else:
        return render_template("login.html",error="Sorry!You need to login first.")
    
@app.route("/add_review/<string:book_isbn>",methods=["POST","GET"])
def add_review(book_isbn):
    if 'username' in session:
        review=request.args.get("book-review")
        rating=request.args.get("star")
        today=date.today()
        username=session["username"]
        r=db.execute("SELECT * from REVIEWS WHERE isbn LIKE :book_isbn AND username LIKE :username",{"book_isbn":book_isbn,"username":username}).fetchone()
        response=requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "tbXVzxEr1fASz9erp54tw", "isbns": book_isbn})
        content=response.json()['books'][0]
        if r is None:   
            db.execute("INSERT INTO REVIEWS(username,isbn,rating,reviews,r_date) VALUES(:username,:isbn,:rating,:reviews,:r_date)",{"username":username,"isbn":book_isbn,"rating":rating,"reviews":review,"r_date":today})
            db.commit()
            return redirect(url_for('view_review',book_isbn=book_isbn))
        else:
            res=db.execute("SELECT * FROM BOOKS WHERE isbn LIKE :book_isbn",{"book_isbn":book_isbn}).fetchone()
            r=db.execute("SELECT * FROM REVIEWS WHERE isbn LIKE :book_isbn",{"book_isbn":book_isbn})
            return render_template("book.html",error="You have already reviewed this book.",res=res,r=r,content=content)
        
    else:
        return render_template("login.html",error="Sorry! You need to login first.")

@app.route("/view_review/<string:book_isbn>",methods=["POST","GET"])
def view_review(book_isbn):
    if 'username' in session:
        r=db.execute("SELECT * from REVIEWS WHERE isbn LIKE :book_isbn",{"book_isbn":book_isbn}).fetchall()
        res=db.execute("SELECT * FROM BOOKS WHERE isbn LIKE :book_isbn",{"book_isbn":book_isbn}).fetchone()
        response=requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "tbXVzxEr1fASz9erp54tw", "isbns": book_isbn})
        content=response.json()['books'][0]
        if r:
            return render_template("book.html",r=r,res=res,content=content)
        else: 
            return render_template("book.html",res=res,content=content)
    else:
        return render_template("login.html",error="Sorry! You need to login first.")

@app.route('/api/<string:book_isbn>',methods=["GET"])
def bookapi(book_isbn):
    
    book=db.execute("SELECT * FROM BOOKS WHERE isbn LIKE :book_isbn ",{"book_isbn":book_isbn}).fetchone()
    if book is not None:
        response=requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "tbXVzxEr1fASz9erp54tw", "isbns": f'{book_isbn}'})
        response.raise_for_status()
        print(response.text)
        content=response.json()
        info={
            "title":book.title,
            "author":book.author,
            "year":book.year,
            "isbn":book_isbn,
            "average_score":content['books'][0]['average_rating'],
            "review_count":content['books'][0]['ratings_count']
        }
        return info
    else:
        abort(404)