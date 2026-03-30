# GitHub Release Checklist

- Create a new GitHub repository.
- Push this codebase to the repository.
- Add a short repository description.
- Add topics such as `llm`, `agents`, `memory`, `benchmarking`, `python`.
- Upload or reference `docs/warm_memory_guide.html` screenshots in the README or repository social preview.
- Verify that `LICENSE`, `README.md`, and `CONTRIBUTING.md` render correctly.
- Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/run_benchmark.py
```

- Commit the generated report in `reports/warm_memory_benchmark.md`.
- Tag the first public release as `v0.1.0`.
- Use the LinkedIn draft in `docs/linkedin_post.md` as the basis for your announcement.
