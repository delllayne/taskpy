from pydantic import BaseModel
from typing import List, Optional

class Movietop(BaseModel):
    name: str
    id: int
    cost: int
    director: str
    description: Optional[str] = None
    cover_filename: Optional[str] = None
    is_available: bool = True  # логическое поле для формы