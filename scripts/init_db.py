# /scripts/init_db.py
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from core.config import settings
from models import Base # Импортируем Base, чтобы загрузить все модели


async def init_db():
    # Установим уровень логирования для отладки
    logging.basicConfig(level=logging.INFO)
    
    engine = create_async_engine(settings.DATABASE_URL)
    
    max_retries = 10
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"Attempting to connect and create tables, attempt {attempt + 1}/{max_retries}")
            
            # Создаем таблицы в транзакции
            async with engine.begin() as conn:
                print("Connected to database successfully")
                
                # Создаем все таблицы
                print("Creating tables...")
                await conn.run_sync(Base.metadata.create_all)
                print("Tables created successfully")
                
                # Проверим, что таблицы созданы
                result = await conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """))
                tables = [row[0] for row in result]
                print(f"Tables in database after creation: {tables}")
                
                if tables:
                    print("✅ Tables successfully created and visible in database!")
                    break # Успешно создали, выходим
                else:
                    print("❌ No tables found after creation attempt")
                    
        except Exception as e:
            print(f"Database initialization attempt {attempt + 1} failed: {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                print(f"Waiting {retry_delay} seconds before next attempt...")
                await asyncio.sleep(retry_delay)
            else:
                print("Failed to initialize database after all attempts")
                raise e
    
    await engine.dispose()
    print("Engine disposed")


if __name__ == "__main__":
    asyncio.run(init_db())