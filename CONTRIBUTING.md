# Contributing to VidkNot

Thank you for your interest in contributing to VidkNot!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/vidknot/vidknot.git
   cd vidknot
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   .\venv\Scripts\activate   # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Copy environment template:
   ```bash
   cp .env.example .env
   ```

## Branch Strategy

- `main` - Stable release branch
- `develop` - Development branch for new features
- Feature branches: `feature/your-feature-name`
- Bugfix branches: `fix/your-bugfix-name`

## Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat(transcriber): add SiliconFlow ASR support
fix(downloader): handle cookie database lock error
docs(readme): update installation instructions
```

## Code Style

- We use `ruff` for linting
- Follow PEP 8 guidelines
- Add type annotations to new functions
- Write docstrings for public APIs

Run linting:
```bash
ruff check src/
```

## Testing

Write tests for new features:
```bash
pytest tests/ -v
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `develop`
3. Make your changes with passing tests
4. Submit a pull request to `develop`

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include your environment details (OS, Python version)
- Provide reproduction steps for bugs

## Questions?

Feel free to open a discussion on GitHub!
