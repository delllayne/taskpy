import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from models import Movietop
import shutil


app = FastAPI()
templates = Jinja2Templates(directory="templates")


MOVIES: List[Movietop] = []
SESSIONS: Dict[str, dict] = {}  # session_token -> {user, created_at}


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)



async def get_current_user(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token or session_token not in SESSIONS:
        return None

    session = SESSIONS[session_token]
    now = datetime.utcnow()


    if now - session["created_at"] > timedelta(minutes=2):
        del SESSIONS[session_token]
        return None


    SESSIONS[session_token]["created_at"] = now
    return session


@app.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, current_user: Optional[dict] = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user["user"],
        "login_time": current_user["created_at"],
        "movies": MOVIES
    })


@app.post("/login")
async def login(
        request: Request,
        response: Response,
        username: str = Form(...),
        password: str = Form(...)
):

    if username == "admin" and password == "secret":
        session_token = str(uuid.uuid4())
        SESSIONS[session_token] = {
            "user": username,
            "created_at": datetime.utcnow()
        }
        response = RedirectResponse(url="/profile", status_code=303)
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=10  # 2 минуты
        )
        return response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверный логин или пароль"
        })


@app.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/")
    response.delete_cookie("session_token")
    return response



MOVIES.extend([
    Movietop(name="Inception", id=1, cost=150, director="Christopher Nolan"),
    Movietop(name="The Matrix", id=2, cost=120, director="Wachowskis"),
    Movietop(name="Interstellar", id=3, cost=200, director="Christopher Nolan"),
    Movietop(name="Pulp Fiction", id=4, cost=90, director="Quentin Tarantino"),
    Movietop(name="The Godfather", id=5, cost=180, director="Francis Ford Coppola"),
    Movietop(name="Forrest Gump", id=6, cost=100, director="Robert Zemeckis"),
    Movietop(name="The Dark Knight", id=7, cost=160, director="Christopher Nolan"),
    Movietop(name="Fight Club", id=8, cost=110, director="David Fincher"),
    Movietop(name="Goodfellas", id=9, cost=130, director="Martin Scorsese"),
    Movietop(name="Schindler's List", id=10, cost=200, director="Steven Spielberg"),
])

MOVIE_DICT = {m.name.lower(): m for m in MOVIES}



@app.get("/movietop/{movie_name}")
def get_movie(movie_name: str):
    movie = MOVIE_DICT.get(movie_name.lower())
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie



@app.get("/add_movie_form", response_class=HTMLResponse)
def add_movie_form():
    return """
    <html>
        <body>
            <h2>Добавить фильм</h2>
            <form action="/add_movie" method="post" enctype="multipart/form-data">
                Название: <input name="name" type="text" required><br><br>
                Режиссёр: <input name="director" type="text" required><br><br>
                Стоимость: <input name="cost" type="number" required><br><br>
                Доступен: <input name="is_available" type="checkbox" value="true"><br><br>
                Описание (файл .txt): <input name="description_file" type="file" accept=".txt"><br><br>
                Обложка (изображение): <input name="cover_file" type="file" accept="image/*"><br><br>
                <input type="submit" value="Добавить">
            </form>
        </body>
    </html>
    """


@app.post("/add_movie")
async def add_movie(
        name: str = Form(...),
        director: str = Form(...),
        cost: int = Form(...),
        is_available: bool = Form(False),
        description_file: Optional[UploadFile] = File(None),
        cover_file: Optional[UploadFile] = File(None)
):

    new_id = max(m.id for m in MOVIES) + 1 if MOVIES else 11

    description = None
    cover_filename = None


    if description_file:
        desc_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.txt")
        with open(desc_path, "wb") as f:
            shutil.copyfileobj(description_file.file, f)
        with open(desc_path, "r", encoding="utf-8") as f:
            description = f.read()


    if cover_file:
        ext = cover_file.filename.split('.')[-1] if '.' in cover_file.filename else 'jpg'
        cover_filename = f"{uuid.uuid4()}.{ext}"
        cover_path = os.path.join(UPLOAD_DIR, cover_filename)
        with open(cover_path, "wb") as f:
            shutil.copyfileobj(cover_file.file, f)

    new_movie = Movietop(
        name=name,
        id=new_id,
        cost=cost,
        director=director,
        description=description,
        cover_filename=cover_filename,
        is_available=is_available
    )

    MOVIES.append(new_movie)
    MOVIE_DICT[new_movie.name.lower()] = new_movie

    return JSONResponse(content={"message": "Фильм добавлен", "movie": new_movie.dict()})



@app.get("/movie/{movie_name}", response_class=HTMLResponse)
def view_movie_with_photo(request: Request, movie_name: str):
    movie = MOVIE_DICT.get(movie_name.lower())
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    cover_url = f"/uploads/{movie.cover_filename}" if movie.cover_filename else None

    return templates.TemplateResponse("movie.html", {
        "request": request,
        "movie": movie,
        "cover_url": cover_url
    })


@app.get("/user")
async def user_profile(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token or session_token not in SESSIONS:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    session = SESSIONS[session_token]
    now = datetime.utcnow()


    if now - session["created_at"] > timedelta(minutes=2):
        del SESSIONS[session_token]
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})


    SESSIONS[session_token]["created_at"] = now

    return {
        "user": session["user"],
        "authorized_at": session["created_at"].isoformat(),
        "current_time": now.isoformat(),
        "movies": [m.dict() for m in MOVIES]
    }



app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")