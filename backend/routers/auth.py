
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.schemas.auth import RegisterRequest, AuthResponse

from fastapi import APIRouter

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)





class UserRecord:                                                                                                                                                                          
    def __init__(self, username: str, password: str, email: str):                                                                                                                          
        self.username = username                                                                                                                                                           
        self.password = password                                                                                                                                                           
        self.email = email                                                                                                                                                                 
                                                                                                                                                                                                 
Users = {1: UserRecord(username = "JohnDoe123", password = "axsdcwAJD", email = "JohnDoe123@email.com")}                                                                                   
UsersByEmail = {"JohnDoe123@email.com": 1} 

@router.post("/register", response_model = AuthResponse)
def register(body : RegisterRequest):
    global Users
    next_id = max(Users) + 1                                                                                                                                                                        
    if body.email in UsersByEmail:                                                                                                                                                         
        raise HTTPException(status_code=409, detail="Email already registered")  
    
    Users[next_id] = UserRecord(username = body.username, password = body.password, email = body.email)
    UsersByEmail[body.email] = next_id
    return AuthResponse(message = "User registered successfully", user_id = next_id) 