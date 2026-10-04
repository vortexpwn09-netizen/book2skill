"""Book2Skill package."""

from .auth import authenticate_user, create_user, list_users
from .core.compiler import build_skill_package, write_json, write_skill_markdown
from .core.extractor import extract_title
from .core.ingestion import read_text_file
from .jobs import ProcessingJob, create_processing_job, get_job, process_job
from .projects import ProjectStore, add_document, create_project, get_project
from .storage import SQLiteStore

__all__ = [
    "build_skill_package",
    "extract_title",
    "read_text_file",
    "write_json",
    "write_skill_markdown",
    "ProcessingJob",
    "create_processing_job",
    "get_job",
    "process_job",
    "ProjectStore",
    "create_project",
    "add_document",
    "get_project",
    "SQLiteStore",
    "create_user",
    "authenticate_user",
    "list_users",
]
