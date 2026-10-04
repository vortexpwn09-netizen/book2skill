from book2skill.projects import ProjectStore, create_project, add_document, get_project


def test_project_store_lifecycle():
    store = ProjectStore()
    project = create_project(store, "Alpha Project")
    assert project["id"]
    assert project["name"] == "Alpha Project"

    doc = add_document(store, project["id"], "sample.md", "# Sample\n\nAI agents use context.")
    assert doc["filename"] == "sample.md"

    retrieved = get_project(store, project["id"])
    assert retrieved["name"] == "Alpha Project"
    assert len(retrieved["documents"]) == 1
