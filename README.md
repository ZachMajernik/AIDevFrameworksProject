Project: Your First API — Project Kickoff
This is a small project where I implement a simple API that uses basic crud operations through routs to interact with an in-memory database

Github repository link:
https://github.com/ZachMajernik/AIDevFrameworksProject

Installing dependancies:
run "pip install -r requirements.txt" in the command line of the project file

Running server:
run "uvicorn main:app --reload" in the command line of the project file

Available endpoints:
http://127.0.0.1:8000/items         (get)
http://127.0.0.1:8000/items/{id}    (get)
http://127.0.0.1:8000/items         (post)
http://127.0.0.1:8000/items/{id}    (put)
http://127.0.0.1:8000/items/{id}    (delete)