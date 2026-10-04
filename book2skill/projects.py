from __future__ import annotations

from typing import Any
from uuid import uuid4


class ProjectStore:
    def __init__(self) -> None:
        self.projects: dict[str, dict[str, Any]] = {}

    def create_project(self, name: str) -> dict[str, Any]:
        project_id = uuid4().hex
        project = {
            "id": project_id,
            "name": name,
            "documents": [],
        }
        self.projects[project_id] = project
        return project

    def add_document(self, project_id: str, filename: str, content: str) -> dict[str, Any]:
        project = self.projects.get(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")

        document = {
            "id": uuid4().hex,
            "filename": filename,
            "content": content,
        }
        project["documents"].append(document)
        return document

    def get_project(self, project_id: str) -> dict[str, Any]:
        project = self.projects.get(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return project


def create_project(store: ProjectStore, name: str) -> dict[str, Any]:
    return store.create_project(name)


def add_document(store: ProjectStore, project_id: str, filename: str, content: str) -> dict[str, Any]:
    return store.add_document(project_id, filename, content)


def get_project(store: ProjectStore, project_id: str) -> dict[str, Any]:
    return store.get_project(project_id)
