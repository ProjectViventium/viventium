# Contributing to Viventium

Thank you for your interest in contributing to Viventium. This document
describes the public contribution flow for the main product repo.

## Getting Started

1. Fork the repository and clone your fork.
2. Read:
   - `README.md`
   - `docs/04_SETUP_GUIDE.md`
   - `docs/05_ENVIRONMENT.md`
   - `docs/requirements_and_learnings/01_Key_Principles.md`
3. Run the installer or doctor flow:

```bash
./install.sh
bin/viventium doctor
```

## Development Principles

We follow these core principles:

### 1. Beautifully Simple
- Don't overcomplicate things
- Seek elegant, efficient solutions
- Study the codebase before adding new patterns

### 2. Single Source of Truth
- Avoid code duplication
- Use existing abstractions when possible
- Follow the DRY principle

### 3. Separation of Concerns
- Keep modules focused on their responsibility
- Clear modular boundaries
- Each component should do one thing well

### 4. Dynamic Configuration
- Avoid hardcoding values
- Use environment variables for configuration
- Make code extensible without modification

## How to Contribute

### Reporting Bugs

- Use the GitHub issue tracker
- Include a clear description of the bug
- Provide steps to reproduce
- Include relevant logs or error messages
- Mention your environment (OS, Python version, etc.)

### Suggesting Features

- Open an issue with the `enhancement` label
- Describe the use case and motivation
- Explain how it fits with the brain-inspired architecture
- Consider how it impacts existing cortices

### Submitting Code

1. Create a branch from `main`.
2. Make the smallest coherent change that solves one problem.
3. Add or update tests.
4. Update the matching doc in `docs/requirements_and_learnings/` when behavior changes.
5. Run the relevant checks:

```bash
python3 -m pytest tests/release/test_config_compiler.py -q
```

Additional component-specific checks:

```bash
cd viventium_v0_4/telegram-viventium && pytest
cd viventium_v0_4/voice-gateway && python3 -m pytest tests -q
```

6. Commit with a clear single-line message.
7. Open a pull request that explains:
   - what changed,
   - why,
   - what was tested,
   - any follow-up work or limitations.

## Code Style

- **Python**: Follow PEP 8, use type hints
- **Imports**: Group by standard library, third-party, local
- **Docstrings**: Use Google style docstrings
- **Comments**: Explain *why*, not *what*

## Testing

- Write unit tests for new functionality
- Integration tests for orchestration changes
- Run the full test suite before submitting

## Documentation

- Update relevant docs when changing functionality
- Add docstrings to public functions and classes
- Keep the README up to date

## Code Review Process

1. All submissions require review
2. Maintainers will review for:
   - Code quality and style
   - Test coverage
   - Documentation
   - Alignment with architecture principles
3. Address feedback and update your PR
4. Once approved, your code will be merged

## Questions?

- Open an issue for questions
- See [Troubleshooting](./docs/06_TROUBLESHOOTING.md) for common issues
- Review existing issues and PRs for context

## License

By contributing to the main `viventium` repo, you agree that your contributions
will be licensed under the project `LICENSE`. Public component repos keep their
own upstream-compatible licenses. See `LICENSE-MATRIX.md`.
