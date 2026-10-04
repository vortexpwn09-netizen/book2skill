from book2skill.jobs import ProcessingJob, process_job


def test_processing_job_lifecycle():
    job = ProcessingJob(title="Deep Work", source_text="AI agents use context and memory. Principle: keep it focused. Method: plan and execute.")

    result = process_job(job)

    assert job.status == "completed"
    assert job.package["title"] == "Deep Work"
    assert "concepts" in job.package
    assert "principles" in job.package
    assert "methods" in job.package
    assert result["title"] == "Deep Work"
