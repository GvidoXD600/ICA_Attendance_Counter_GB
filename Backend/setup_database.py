import asyncio

from database import Base, engine
from models import FaceSample, Lecturer, Session, Student


async def create_tables():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


asyncio.run(create_tables())