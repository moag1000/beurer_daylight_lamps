# Contributing to Beurer Daylight Lamps

Thanks for your interest in contributing! This document provides guidelines for contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a new branch for your changes

## Development Setup

### Prerequisites

- Python 3.11+
- Home Assistant development environment (optional but recommended)

### Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install test dependencies
pip install -r requirements_test.txt
```

### Running Tests

```bash
pytest tests/ -v
```

## Code Style

- Follow [Home Assistant's style guidelines](https://developers.home-assistant.io/docs/development_guidelines)
- Use type hints for all function parameters and return values
- Keep code simple and readable
- Add docstrings to classes and functions

## Pull Request Process

1. **Create a feature branch** from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Keep commits focused and atomic
   - Write clear commit messages

3. **Test your changes**
   - Run existing tests: `pytest tests/ -v`
   - Add new tests for new functionality
   - Test manually with a real device if possible

4. **Update documentation**
   - Update README.md if adding new features
   - Update CHANGELOG.md with your changes

5. **Submit a Pull Request**
   - Fill out the PR template
   - Reference any related issues
   - Be responsive to feedback

## Reporting Issues

- Use the issue templates provided
- Include debug logs when reporting bugs
- Include diagnostics export if possible
- Check existing issues before creating a new one

## Testing with a Real Device

If you have a Beurer daylight lamp (TL50, TL70, TL80, TL90, TL100):

1. Enable debug logging in Home Assistant:
   ```yaml
   logger:
     logs:
       custom_components.beurer_daylight_lamps: debug
   ```

2. Test the following scenarios:
   - Device discovery
   - On/Off control
   - Brightness control
   - RGB color changes
   - Effects
   - Reconnection after disconnect

## Code of Conduct

- Be respectful and constructive
- Focus on the code, not the person
- Help others learn and grow

## Questions?

Open a discussion or issue if you have questions about contributing.
