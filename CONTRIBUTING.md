# Contributing to Cora AI

We welcome contributions! Please follow these guidelines:

## Code of Conduct
Please be respectful and considerate of others when contributing.

## Development Setup
1. Ensure you have Python 3.11+ and Node 22+ installed.
2. Install Python dependencies: `pip install -r requirements.txt`
3. Install Node dependencies: `cd frontend && npm install`
4. Set up your `.env` file from `.env.example`

## Making Changes
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write or update tests as appropriate
5. Run linting:
   - Python: `ruff check src/`
   - Frontend: `npm run lint`
6. Submit a Pull Request

## Architecture Rules
- Do not introduce new external cloud dependencies.
- Ensure any new APIs are placed under `/v1/`.
- Pluggable interfaces (like `SearchProvider`) must have at least one open-source or local implementation alternative.
- Migrations must be added as `.sql` files in the `migrations/` directory.

Thank you for contributing!