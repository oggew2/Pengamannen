# Contributing to Börslabbet App

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/borslabbet-app.git
   cd borslabbet-app
   ```

3. Set up backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

4. Set up frontend:
   ```bash
   cd frontend
   npm install
   ```

## Code Style

- Python: Follow PEP 8
- TypeScript: Use ESLint defaults
- Commit messages: Use conventional commits (feat:, fix:, docs:, etc.)

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run tests: `cd backend && pytest`
4. Type check frontend: `cd frontend && npx tsc --noEmit`
5. Commit with descriptive message
6. Push and create PR

## Reporting Issues

Please include:
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version, Node version)
