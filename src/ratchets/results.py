from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class MatchResult:
    file: str
    line: Optional[int]
    content: str
    blame_author: Optional[str] = None
    blame_time: Optional[datetime] = None


@dataclass
class TestResult:
    name: str
    matches: List[MatchResult]
