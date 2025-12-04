# Contributing to Food Barcode Scanner

Thank you for your interest in contributing to the Food Barcode Scanner project!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/food_scanner.git`
3. Create a virtual environment: `python -m venv venv`
4. Install dependencies: `pip install -r requirements.txt`
5. Install dev dependencies: `pip install black isort flake8 pytest pytest-cov`

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests: `python -m pytest tests/ -v`
4. Format code: `black src/ tests/` and `isort src/ tests/`
5. Check linting: `flake8 src/ tests/`
6. Commit your changes with a descriptive message
7. Push to your fork and create a Pull Request

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write docstrings for all public functions and classes
- Keep functions focused and small
- Use meaningful variable names

## Testing

- Write tests for new features
- Maintain or improve test coverage
- Test edge cases and error conditions

## Adding New Additives

To add new additive mappings:

1. Edit `data/additives_mapping.json`
2. Follow the existing format:

```json
{
  "E123": {
    "name": "Additive Name",
    "concern": "High|Moderate|Minimal|Low Value",
    "category": "Category",
    "description": "Description of the additive"
  }
}
```

3. Add tests if needed
4. Update documentation

## Reporting Bugs

- Use the GitHub issue tracker
- Include steps to reproduce
- Include your Python version and OS
- Attach relevant logs or screenshots

## Feature Requests

- Check existing issues first
- Describe the use case clearly
- Be open to discussion about implementation

## Questions?

Feel free to open an issue for any questions about contributing.
