# Telegram Test Bot - Replit Edition

## Project Overview

This is a Telegram bot for educational testing and assessment using the Rasch Model Item Response Theory (IRT). The bot allows administrators to create tests, students to take them, and provides scientific assessment using IRT methodologies.

**Current State**: ✅ Running and operational on Replit

**Last Updated**: November 17, 2024

## Project Architecture

### Technology Stack
- **Python 3.11**: Main programming language
- **python-telegram-bot**: Telegram Bot API wrapper
- **NumPy & SciPy**: Scientific computing and statistical analysis
- **Rasch Model IRT**: Educational assessment methodology (fallback JMLE algorithm)
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
├── utils.py                  # Helper functions (subscription check, Rasch scoring, PDF generation)
├── rasch_pkg.py              # Rasch Model IRT implementation
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

4. **Scientific Assessment**
   - Rasch Model IRT analysis
   - T-score calculation: T = 50 + 10Z
   - Student ability (theta) estimation
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
- numpy>=1.21.0
- scipy>=1.7.0
- pytz>=2023.3
- openpyxl>=3.1.0
- reportlab>=3.6.0

**Note**: `rpy2` (R integration) is not installed due to R runtime requirements. The bot automatically uses the fallback JMLE algorithm for Rasch Model calculations.

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
- `/rasch` - Rasch Model student assessment

### Admin Commands
- `/createtest` - Create new tests
- `/tests` - View all tests
- `/rasch` - Rasch Model student assessment

### Student Commands
- `/start` - Register and get started
- `/tests` - View available tests (or use "📝 Test ishlash" button)
- `/myresults` - View personal results (or use "📊 Test natijalarim" button)

## Rasch Model Assessment

The bot implements Item Response Theory using the Rasch Model:

**Formula**: P(X=1|θ, β) = exp(θ - β) / (1 + exp(θ - β))

Where:
- **θ (theta)**: Student ability
- **β (beta)**: Question difficulty

**T-score Calculation**: T = 50 + 10Z
- **Z**: (θ - μ) / σ (standardized score)

**Grading Scale**:
- 🟢 **A (Excellent)**: T ≥ 70
- 🟡 **B (Good)**: 60 ≤ T < 70
- 🟠 **C (Satisfactory)**: 50 ≤ T < 60
- 🔴 **D (Unsatisfactory)**: 40 ≤ T < 50
- ⚫ **E (Very Low)**: T < 40

## Implementation Notes

### Fallback Mechanisms
The bot is designed with robust fallback mechanisms:

1. **Rasch Model**: Uses JMLE algorithm when R/eRm is unavailable
2. **PDF Generation**: Falls back to ReportLab when wkhtmltopdf fails
3. **Error Handling**: Comprehensive error handlers for all operations

### Timezone
All timestamps use Uzbekistan time (Asia/Tashkent, UTC+5)

### Language
The bot interface is in Uzbek language.

## Recent Changes

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
- **Local**: Bot can use R + eRm for more accurate Rasch calculations
- **Replit**: Uses fallback JMLE algorithm (slightly less accurate but still scientifically valid)

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

1. **No R Integration**: rpy2 not installed, using fallback algorithm
2. **Local Storage**: Uses JSON file, not a production database
3. **Single Instance**: One bot instance per Replit deployment
4. **No Rollback**: Data is persisted immediately, no transaction support

## Security Notes

- `config.py` is excluded from git (contains sensitive data)
- Secrets managed via Replit environment variables
- Bot token and user IDs never logged or exposed
- All user data stored locally in `data.json`

## Support & Documentation

- Original README: See `README.md` for detailed usage instructions in Uzbek
- Telegram Documentation: https://core.telegram.org/bots
- Rasch Model Theory: https://en.wikipedia.org/wiki/Rasch_model
