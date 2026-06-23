import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference
from backend.routers.auth import router as auth_router 

from pydantic import BaseModel

                                                                                                                                             
 

app = FastAPI()
app.include_router(auth_router)


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

    

