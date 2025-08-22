# TruthLens - News Summarizer & Bias Detector

A Flask-based web application that analyzes news articles for bias and generates summaries using Perplexity AI API.

## Features

- **News Analysis**: Analyze articles from URLs or direct text input
- **Bias Detection**: AI-powered bias analysis with detailed scoring
- **Summary Generation**: Generate concise summaries in different tones
- **Fake News Detection**: Identify potential misinformation patterns
- **Modern UI**: Beautiful, responsive interface with real-time analysis

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the project root with your Perplexity API keys:

```env
# Perplexity API Keys
PERPLEXITY_URL_API_KEY=your_perplexity_api_key_here
PERPLEXITY_TEXT_API_KEY=your_perplexity_api_key_here

# Optional: Flask secret key
SECRET_KEY=your_secret_key_here
```

### 3. Get Perplexity API Keys

1. Visit [Perplexity AI](https://www.perplexity.ai/)
2. Sign up for an account
3. Navigate to API settings
4. Generate your API key
5. Add the key to your `.env` file

### 4. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## API Configuration

The application supports two separate API keys:
- **URL API Key**: Used for analyzing articles from URLs
- **Text API Key**: Used for analyzing direct text input

You can use the same API key for both, or different keys for different use cases.

## Usage

1. **URL Analysis**: Paste a news article URL and click "Analyze"
2. **Text Analysis**: Paste article text directly and click "Analyze"
3. **Tone Selection**: Choose from different summary tones (neutral, etc.)
4. **Results**: View summary, bias score, sentiment analysis, and detailed breakdown

## Health Check

Visit `/health` to check the status of your API configuration and system health.

## Technologies Used

- **Backend**: Flask, Python
- **AI**: Perplexity AI API (llama-3.1-sonar-small-128k-online model)
- **Web Scraping**: BeautifulSoup4, Requests
- **Frontend**: HTML, CSS, JavaScript
- **Styling**: Modern CSS with gradients and animations

## Notes

- The application uses Perplexity's `llama-3.1-sonar-small-128k-online` model for both summarization and bias analysis
- URL extraction includes robust error handling for various website structures
- Bias analysis includes pattern detection for obvious fake news indicators
- All API calls include proper timeout and error handling

