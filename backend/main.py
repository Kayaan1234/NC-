import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference
from backend.routers.auth import router as auth_router 
from backend.routers.users import router as user_router



from backend.database import engine, Base

Base.metadata.create_all(bind=engine) #creates the database tables based on the defined models if they don't already exist
                                                                                                                                             
 

app = FastAPI()
app.include_router(auth_router)
app.include_router(user_router)


origins = [
    "https://localhost:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],)

@app.get("/scalar")
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title = "Scalar API",
    )

    

