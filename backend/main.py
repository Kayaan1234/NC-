import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference
import schemas

from pydantic import BaseModel

class UserRecord:                                                                                                                                                                          
    def __init__(self, username: str, password: str, email: str):                                                                                                                          
        self.username = username                                                                                                                                                           
        self.password = password                                                                                                                                                           
        self.email = email                                                                                                                                                                 
                                                                                                                                                                                                 
Users = {1: UserRecord(username = "JohnDoe123", password = "axsdcwAJD", email = "JohnDoe123@email.com")}                                                                                   
UsersByEmail = {"JohnDoe123@email.com": 1}                                                                                                                                                 
 

app = FastAPI()

origins = [
    "https://localhost:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],)

@app.get("/scalar")
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title = "Scalar API",
    )

@app.post("/auth/register", response_model = schemas.AuthResponse)
def register(body : schemas.RegisterRequest):
    global Users
    next_id = max(Users) + 1                                                                                                                                                                        
    if body.email in UsersByEmail:                                                                                                                                                         
        raise HTTPException(status_code=409, detail="Email already registered")  
    
    Users[next_id] = UserRecord(username = body.username, password = body.password, email = body.email)
    UsersByEmail[body.email] = next_id
    return schemas.AuthResponse(message = "User registered successfully", user_id = next_id)     

