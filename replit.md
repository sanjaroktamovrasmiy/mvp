# Telegram Test Bot - Replit Edition

## Project Overview

This is a Telegram bot for educational testing and assessment. The bot allows administrators to create tests, students to take them, and provides percentage-based scoring and results.

**Current State**: ✅ Running and operational on Replit

**Last Updated**: November 17, 2025

## Project Architecture

### Technology Stack
- **Python 3.11**: Main programming language
- **python-telegram-bot**: Telegram Bot API wrapper
- **ReportLab**: PDF generation for test results
- **PDFKit + wkhtmltopdf**: HTML to PDF conversion
- **OpenPyXL**: Excel file processing for test matrices
- **PyTZ**: Timezone handling (Uzbekistan time)

### Project Structure
```
.
├── bot.py                    # Main bot entry point
├── config.py                 # Configuration (reads from env vars)
├── database.py               # JSON-based data persistence
├── handlers.py               # All Telegram command and callback handlers
├── utils.py                  # Helper functions (subscription check, PDF generation)
├── requirements.txt          # Python dependencies
├── data.json                 # Runtime data storage (auto-generated)
└── README.md                 # Original project documentation
```

## Key Features

1. **Role-Based Access Control**
   - Boss: Full administrative access
   - Admins: Test creation and student assessment
   - Students: Test taking and results viewing

2. **Mandatory Channel Subscription**
   - Enforces channel membership before bot access
   - Configurable channel list

3. **Test Management**
   - Text-based test creation (formatted input)
   - Multiple choice questions (a, b, c, d)
   - One-time test attempts per student
   - Answer format: 1a2b3c4d...

4. **Assessment & Reporting**
   - Percentage-based scoring
   - PDF reports with detailed statistics
   - Excel matrix export (0-1 format)

5. **User Management**
   - First name and last name collection
   - User data persistence
   - Results tracking per student

## Replit-Specific Configuration

### Environment Variables (Secrets)
The following secrets are configured in Replit and must be set:

- **BOT_TOKEN**: Telegram bot token from @BotFather
- **BOSS_ID**: Telegram user ID with full administrative access

### Workflow
- **Name**: `telegram-bot`
- **Command**: `python bot.py`
- **Type**: Console (background service)
- **Status**: Always running to respond to Telegram messages

### Dependencies
All Python packages are managed via pip and defined in `requirements.txt`:
- python-telegram-bot==20.7
- pdfkit==1.0.0
- pytz>=2023.3
- openpyxl>=3.1.0
- reportlab>=3.6.0

### System Packages
- **wkhtmltopdf**: HTML to PDF conversion utility

## Data Storage

### data.json Structure
```json
{
  "admins": [],
  "mandatory_channels": [],
  "tests": {},
  "user_results": {},
  "users": {}
}
```

This file is auto-generated and persisted locally. It's excluded from git via `.gitignore`.

## Bot Commands

### Boss Commands
- `/admin` - Manage administrators
- `/channels` - Manage mandatory channels
- `/createtest` - Create new tests

### Admin Commands
- `/createtest` - Create new tests
- `/tests` - View all tests

### Student Commands
- `/start` - Register and get started
- `/tests` - View available tests (or use "📝 Test ishlash" button)
- `/myresults` - View personal results (or use "📊 Test natijalarim" button)

## Implementation Notes

### Fallback Mechanisms
The bot is designed with robust fallback mechanisms:

1. **PDF Generation**: Falls back to ReportLab when wkhtmltopdf fails
2. **Error Handling**: Comprehensive error handlers for all operations

### Timezone
All timestamps use Uzbekistan time (Asia/Tashkent, UTC+5)

### Language
The bot interface is in Uzbek language.

## Recent Changes

### November 17, 2025 - Complete System Overhaul for Auto-Grading
- **All questions (1-43) now auto-graded**: Removed manual review requirement
- **Test submission flow fixed**: Added 41-43 question answer input functionality
- **Matrix export redesigned** in `utils.py`:
  - Sheet 1: "Questions 1-40" - 0/1 matrix for all multiple choice and text questions
  - Sheet 2: "Questions 41-43" - 0/1 matrix for problem-based questions (separate sheet)
  - All questions use 0/1 format (no more N/A or None values)
  - Matrix files include timestamp: `matrix_{test_id}_{timestamp}.xlsx`
- **Auto-grading implementation** in `handlers.py`:
  - Questions 1-35: Multiple choice (exact match)
  - Questions 36-40: Text answers (case-insensitive comparison)
  - Questions 41-43: Problem answers (comma-separated, case-insensitive, all sub-answers must match)
- **Test flow improvements**:
  - Step 1: Enter answers for questions 1-35 (e.g., 1a2b3c4d...)
  - Step 2: Enter answers for questions 36-40 (one per line)
  - Step 3: Enter answers for questions 41-43 (one per line for all sub-questions)
  - Added `waiting_problem_answers` state for proper flow control
- **Percentage calculation**: Now based on all 43 questions (not just 1-35)

### November 17, 2025 - Rasch Model Removal
- Removed Rasch Model IRT implementation completely
- Switched to simple percentage-based scoring
- Removed `/rasch` command and Rasch matrix evaluation feature
- Updated PDF reports to show only percentage scores
- Removed rasch_pkg.py file and all Rasch-related functions
- Test results now sorted by percentage instead of Rasch T-score
- Simplified dependencies (removed NumPy, SciPy requirements)

### November 17, 2024 - Test Format Customization
- Confirmed bot supports A-F answer options for questions 33-35 (6 variants)
- Enhanced documentation for extended multiple-choice question format
- Questions 1-32: 4 answer options (A-D)
- Questions 33-35: 6 answer options (A-F) for matching/alignment questions
- Questions 36-40: Text-based answers for calculation problems

### November 17, 2024 - Initial Replit Setup
- Installed Python 3.11 and all dependencies
- Created `config.py` to read from Replit environment variables
- Configured secrets (BOT_TOKEN, BOSS_ID)
- Set up workflow to run bot continuously
- Installed wkhtmltopdf for PDF generation
- Fixed async handler bug in `/cancel` command (was returning None instead of awaitable)
- Verified bot is running without errors and connected to Telegram API

## Development Notes

### Running Locally vs Replit
- Bot uses simple percentage-based scoring for all test results
- All features work identically on Replit and local environments

### Adding New Features
When extending the bot:
1. Add handlers in `handlers.py`
2. Register handlers in `bot.py`
3. Update data schema in `database.py` if needed
4. Add helper functions to `utils.py`

### Debugging
- Check workflow logs in Replit console
- Review `bot.log` file (if generated)
- Use Telegram's error messages from BotFather

## Known Limitations

1. **Local Storage**: Uses JSON file, not a production database
2. **Single Instance**: One bot instance per Replit deployment
3. **No Rollback**: Data is persisted immediately, no transaction support

## Security Notes

- `config.py` is excluded from git (contains sensitive data)
- Secrets managed via Replit environment variables
- Bot token and user IDs never logged or exposed
- All user data stored locally in `data.json`

## Support & Documentation

- Original README: See `README.md` for detailed usage instructions in Uzbek
- Telegram Documentation: https://core.telegram.org/bots
