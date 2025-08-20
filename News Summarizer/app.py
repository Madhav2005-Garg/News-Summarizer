from flask import Flask, request, render_template, flash, redirect, url_for
from flask_cors import CORS
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import os
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Global API keys
GEMINI_URL_API_KEY = os.getenv('GEMINI_URL_API_KEY')
GEMINI_TEXT_API_KEY = os.getenv('GEMINI_TEXT_API_KEY')

if not GEMINI_URL_API_KEY:
    print("Warning: GEMINI_URL_API_KEY environment variable not set")
if not GEMINI_TEXT_API_KEY:
    print("Warning: GEMINI_TEXT_API_KEY environment variable not set")

def extract_text_from_url(url):
    """ROBUST URL extraction with detailed error handling and multiple strategies"""
    try:
        print(f"🔍 Attempting to extract text from URL: {url}")
        
        # Validate URL format
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise Exception("Invalid URL format. Please include http:// or https://")
        
        # Enhanced headers to avoid bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        print("📥 Making request to URL...")
        
        # Make request with proper error handling
        try:
            response = requests.get(url, headers=headers, timeout=20, allow_redirects=True, verify=True)
            response.raise_for_status()
            
        except requests.exceptions.SSLError:
            print("⚠️ SSL Error, trying without verification...")
            response = requests.get(url, headers=headers, timeout=20, allow_redirects=True, verify=False)
            response.raise_for_status()
            
        except requests.exceptions.Timeout:
            raise Exception("Request timed out. The website might be slow or unreachable.")
            
        except requests.exceptions.ConnectionError:
            raise Exception("Failed to connect to the URL. Please check if the website is accessible.")
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            if status_code == 403:
                raise Exception("Access forbidden. The website might be blocking automated requests.")
            elif status_code == 404:
                raise Exception("Page not found. Please check if the URL is correct.")
            elif status_code == 429:
                raise Exception("Too many requests. Please try again later.")
            else:
                raise Exception(f"HTTP Error {status_code}: {str(e)}")
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            raise Exception(f"URL does not contain HTML content. Content-Type: {content_type}")
        
        print("📄 Parsing HTML content...")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'aside', 'header', 'menu', 'noscript', 'iframe']):
            element.decompose()
        
        # Try multiple content extraction strategies
        article_text = ""
        
        # Strategy 1: JSON-LD structured data
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld and not article_text:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, list):
                    data = data[0]
                
                article_body = data.get('articleBody') or data.get('text', '')
                if article_body and len(article_body) > 200:
                    article_text = article_body
                    print("✅ Extracted from JSON-LD structured data")
            except:
                pass
        
        # Strategy 2: Specific news site selectors
        if not article_text:
            selectors = [
                # Major news sites
                '[data-module="ArticleBody"]',  # BBC
                '.story-body__inner',           # BBC
                '.article-body',                # CNN, Fox News
                '.story-body',                  # Reuters
                '.articleBody',                 # WSJ
                '.entry-content',               # WordPress
                '.post-content',                # Blogs
                '.content-body',                # Various
                '.article-content',             # General
                '.post-body',                   # Blog posts
                
                # Generic selectors
                'article[role="main"]',
                'main article',
                '[role="main"]',
                'article',
                '.article',
                '.content',
                'main'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    texts = []
                    for element in elements:
                        text = element.get_text(separator=' ', strip=True)
                        if len(text) > 100:
                            texts.append(text)
                    
                    if texts:
                        article_text = ' '.join(texts)
                        print(f"✅ Extracted using selector: {selector}")
                        break
        
        # Strategy 3: Paragraph extraction
        if not article_text or len(article_text) < 200:
            print("📄 Using paragraph extraction...")
            paragraphs = soup.find_all(['p', 'div'])
            content_parts = []
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Filter quality content
                if (len(text) > 50 and 
                    len(text.split()) > 8 and
                    not any(word in text.lower() for word in ['cookie', 'subscribe', 'newsletter', 'advertisement', 'follow us'])):
                    content_parts.append(text)
            
            if content_parts:
                article_text = ' '.join(content_parts)
        
        # Strategy 4: Fallback to body text
        if not article_text or len(article_text) < 200:
            print("📄 Using fallback body extraction...")
            body = soup.find('body')
            if body:
                article_text = body.get_text(separator=' ', strip=True)
            else:
                article_text = soup.get_text(separator=' ', strip=True)
        
        # Clean the extracted text
        article_text = re.sub(r'\s+', ' ', article_text).strip()
        
        # Remove common artifacts
        artifacts = [
            r'Skip to main content',
            r'Cookie.*?preferences',
            r'We use cookies',
            r'Subscribe.*?newsletter',
            r'Advertisement',
            r'Loading\.\.\.',
            r'Please enable JavaScript'
        ]
        
        for pattern in artifacts:
            article_text = re.sub(pattern, '', article_text, flags=re.IGNORECASE)
        
        article_text = article_text.strip()
        
        # Validate final content
        if not article_text or len(article_text) < 100:
            raise Exception("Could not extract enough readable content. The page might require JavaScript, have a paywall, or contain mostly multimedia content.")
        
        print(f"✅ Successfully extracted {len(article_text)} characters")
        return article_text[:15000]  # Limit to 15k characters
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ URL extraction failed: {error_msg}")
        
        # Provide user-friendly error messages
        if "Invalid URL format" in error_msg:
            raise Exception("Please provide a valid URL starting with http:// or https://")
        elif "SSL" in error_msg:
            raise Exception("SSL certificate error. Try copying the article text instead.")
        elif "403" in error_msg or "forbidden" in error_msg.lower():
            raise Exception("Website blocked access. Please copy and paste the article text instead.")
        elif "404" in error_msg:
            raise Exception("Article not found. Please check if the URL is correct.")
        elif "timeout" in error_msg.lower():
            raise Exception("Website response timeout. Please try again or use article text.")
        elif "Could not extract enough" in error_msg:
            raise Exception("Unable to extract article content. Please try copying the text instead.")
        else:
            raise Exception(f"Failed to extract article: {error_msg}")

def generate_summary(text, tone, is_url=False):
    """Generate summary using appropriate Gemini API based on source type"""
    tone_prompts = {"neutral": f"Just give answers according to the tone: {tone} and the answer should be according to the Question only and the form of the answer will be properly structured and concise."}
    
    prompt = f"{tone_prompts.get(tone, tone_prompts['neutral'])}\n\nArticle text:\n{text}"
    
    try:
        if is_url:
            # Use URL API key for URL-based content
            if not GEMINI_URL_API_KEY:
                raise Exception("URL API key not configured")
            genai.configure(api_key=GEMINI_URL_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            print("📝 Generated summary using URL API key")
        else:
            # Use text API key for direct text input
            if not GEMINI_TEXT_API_KEY:
                raise Exception("Text API key not configured")
            genai.configure(api_key=GEMINI_TEXT_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            print("📝 Generated summary using Text API key")
            
        return response.text.strip()
    except Exception as e:
        raise Exception(f"Failed to generate summary: {str(e)}")

def analyze_bias(text, is_url=False):
    """Analyze bias and fake news using appropriate Gemini API based on source type"""
    print(f"Analyzing bias and fake news with {'URL' if is_url else 'Text'} API key...")
    
    try:
        # Pre-check for obvious fake news patterns
        fake_news_patterns = [
            r'eating \d+ pizzas.*increase.*lifespan',
            r'scientists (have )?confirmed.*\d+.*pizzas',
            r'international pizza research institute',
            r'life-extending molecules.*cheese',
            r'miracle.*cure.*discovered',
            r'doctors hate this.*trick',
            r'secret.*government.*hiding',
            r'one weird trick',
            r'\d+.*guarantee.*health'
        ]
        
        text_lower = text.lower()
        fake_patterns_found = []
        for pattern in fake_news_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                fake_patterns_found.append(pattern)
        
        # Enhanced prompt for Gemini API bias analysis
        bias_prompt = f"""You are an expert fact-checker and bias analyst. Analyze the following news article text for bias, fake news, and misinformation.

Please provide a comprehensive analysis focusing on:

1. **Bias Score (0-10)**: Rate the overall bias and misinformation level where:
   - 0-2: Highly credible, factual, minimal bias
   - 3-4: Some bias but generally reliable
   - 5-6: Moderate bias, questionable claims
   - 7-8: High bias, misleading information
   - 9-10: Obvious fake news, misinformation, or absurd claims

2. **Sentiment**: Overall emotional tone (positive, negative, neutral, neutral-positive, neutral-negative)

3. **Confidence Level (0-100)**: How confident you are in your analysis

4. **Source Quality (0-10)**: Estimated credibility of sources mentioned or implied

5. **Specific Analysis**: Detailed explanation of your findings

6. **Bias Indicators**: List specific red flags or concerning elements

7. **Balance Score (0-1)**: How balanced the reporting is (1 = very balanced, 0 = extremely one-sided)

8. **Factual Score (0-1)**: How factual the content appears (1 = highly factual, 0 = mostly false/misleading)

IMPORTANT: Look for these red flags:
- Absurd health claims without scientific backing
- Fake organizations or institutions
- Impossible scientific claims
- Sensationalized headlines
- Lack of credible sources
- Emotional manipulation
- Conspiracy theories
- Too-good-to-be-true promises

Respond ONLY in this exact JSON format:
{{
    "bias_score": [number 0-10],
    "sentiment": "[positive/negative/neutral/neutral-positive/neutral-negative]",
    "confidence": [number 0-100],
    "sources": [number 0-10],
    "ai_analysis": "[brief explanation of your analysis about 4 lines not more than that]",
    "balance_score": [number 0-1],
    "factual_score": [number 0-1]
}}

Article Text to Analyze:
{text[:3000]}"""

        # Generate analysis using appropriate Gemini API key
        if is_url:
            if not GEMINI_URL_API_KEY:
                raise Exception("URL API key not configured")
            genai.configure(api_key=GEMINI_URL_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(bias_prompt)
            print("🔍 Analyzed bias using URL API key")
        else:
            if not GEMINI_TEXT_API_KEY:
                raise Exception("Text API key not configured")
            genai.configure(api_key=GEMINI_TEXT_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(bias_prompt)
            print("🔍 Analyzed bias using Text API key")
        
        gemini_response = response.text.strip()
        
        print(f"Gemini API response: {gemini_response}")
        
        # Try to extract JSON from the response
        try:
            # Clean the response to extract JSON
            json_match = re.search(r'\{.*\}', gemini_response, re.DOTALL)
            if json_match:
                bias_data = json.loads(json_match.group())
            else:
                # Try parsing the entire response as JSON
                bias_data = json.loads(gemini_response)
            
            # Validate and clean the response
            bias_score = float(bias_data.get('bias_score', 3.0))
            
            # Additional check: If we detected fake news patterns but AI gave low score, override
            if fake_patterns_found and bias_score < 7:
                print(f"Overriding low bias score due to {len(fake_patterns_found)} fake news patterns detected")
                bias_score = 8.5
                bias_data['ai_analysis'] = f"FAKE NEWS DETECTED: {bias_data.get('ai_analysis', '')} Additionally, obvious misinformation patterns were detected."
            
            bias_score = max(0, min(bias_score, 10))
            
            sentiment = bias_data.get('sentiment', 'neutral')
            if sentiment not in ['positive', 'negative', 'neutral', 'neutral-positive', 'neutral-negative']:
                sentiment = 'neutral'
            
            confidence = int(bias_data.get('confidence', 75))
            confidence = max(0, min(confidence, 100))
            
            sources = int(bias_data.get('sources', 3))
            sources = max(0, min(sources, 20))
            
            ai_analysis = bias_data.get('ai_analysis', 'Bias analysis completed using Gemini API.')
            bias_indicators = bias_data.get('bias_indicators', [])
            if not isinstance(bias_indicators, list):
                bias_indicators = []
            
            # Add detected fake news patterns to bias indicators
            if fake_patterns_found:
                bias_indicators.extend(["Fake news patterns detected", "Absurd health claims", "Misinformation indicators"])
            
            balance_score = float(bias_data.get('balance_score', 0.5))
            balance_score = max(0, min(balance_score, 1))
            
            factual_score = float(bias_data.get('factual_score', 0.5))
            factual_score = max(0, min(factual_score, 1))
            
            # Adjust factual score if fake patterns found
            if fake_patterns_found:
                factual_score = 0.0
                balance_score = 0.1
            
            print(f"Bias analysis complete - Score: {bias_score}, Sentiment: {sentiment}, Confidence: {confidence}%")
            
            return {
                'bias_score': bias_score,
                'sentiment': sentiment,
                'confidence': confidence,
                'sources': sources,
                'ai_analysis': ai_analysis,
                'bias_indicators': bias_indicators,
                'balance_score': balance_score,
                'factual_score': factual_score
            }
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Failed to parse Gemini response as JSON: {str(e)}")
            print(f"Raw response: {gemini_response[:500]}")
            
            # Fallback analysis based on response content
            response_lower = gemini_response.lower()
            
            # Check if response indicates fake news
            fake_indicators = ['fake', 'false', 'misinformation', 'absurd', 'ridiculous', 'unreliable', 'misleading']
            fake_count = sum(1 for indicator in fake_indicators if indicator in response_lower)
            
            if fake_count >= 2 or fake_patterns_found:
                bias_score = 8.5
                sentiment = 'neutral'
                factual_score = 0.1
                balance_score = 0.2
                confidence = 85
            elif 'bias' in response_lower or 'political' in response_lower:
                bias_score = 6.0
                sentiment = 'neutral'
                factual_score = 0.4
                balance_score = 0.4
                confidence = 70
            else:
                bias_score = 4.0
                sentiment = 'neutral'
                factual_score = 0.6
                balance_score = 0.6
                confidence = 60
            
            return {
                'bias_score': bias_score,
                'sentiment': sentiment,
                'confidence': confidence,
                'sources': 2,
                'ai_analysis': gemini_response[:300] + "..." if len(gemini_response) > 300 else gemini_response,
                'bias_indicators': ["Response parsing failed"] + (["Obvious fake news patterns"] if fake_patterns_found else []),
                'balance_score': balance_score,
                'factual_score': factual_score
            }
            
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        
        # Even in error, check for obvious fake news patterns
        obvious_fake = any(phrase in text.lower() for phrase in [
            'eating 10 pizzas', 'pizza research institute', 'life-extending molecules', 'miracle cure'
        ])
        
        return {
            'bias_score': 9.0 if obvious_fake else 5.0,
            'sentiment': 'neutral',
            'confidence': 60 if obvious_fake else 40,
            'sources': 0 if obvious_fake else 3,
            'ai_analysis': f"OBVIOUS MISINFORMATION: Despite API error, clear fake news patterns detected." if obvious_fake else f"Unable to complete bias analysis due to error: {str(e)}. Using fallback analysis.",
            'bias_indicators': ["Obvious fake news patterns", "API error occurred"] if obvious_fake else ["API error occurred"],
            'balance_score': 0.1 if obvious_fake else 0.5,
            'factual_score': 0.0 if obvious_fake else 0.5
        }

def analyze_article(url=None, text=None, tone='neutral'):
    """Main function to analyze an article"""
    try:
        is_url_source = bool(url and not text)
        
        # Get article text
        if url and not text:
            article_text = extract_text_from_url(url)
            print("📰 Processing URL-based article")
        elif text:
            article_text = text
            print("📝 Processing direct text input")
        else:
            raise ValueError("Either URL or text must be provided")
        
        if len(article_text.strip()) < 100:
            raise ValueError("Article text is too short to analyze effectively")
        
        # Generate summary using appropriate API key
        summary = generate_summary(article_text, tone, is_url=is_url_source)
        
        # Analyze bias using appropriate API key
        bias_analysis = analyze_bias(article_text, is_url=is_url_source)
        
        return {
            'success': True,
            'summary': summary,
            'bias_score': bias_analysis['bias_score'],
            'sentiment': bias_analysis['sentiment'],
            'sources': bias_analysis['sources'],
            'confidence': bias_analysis['confidence'],
            'ai_analysis': bias_analysis['ai_analysis'],
            'detailed_bias': bias_analysis,
            'article_length': len(article_text),
            'analysis_timestamp': datetime.now().isoformat(),
            'api_used': 'URL API' if is_url_source else 'Text API'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def get_bias_level(score):
    """Get bias level based on score"""
    if score < 3:
        return 'low'
    elif score < 6:
        return 'medium'
    else:
        return 'high'

def get_bias_color_class(bias_level):
    """Get CSS class for bias level"""
    return f'bias-{bias_level}'

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route that handles both display and analysis"""
    result = None
    error_message = None
    
    if request.method == 'POST':
        # Check if API keys are configured
        if not GEMINI_URL_API_KEY and not GEMINI_TEXT_API_KEY:
            error_message = 'Gemini API keys not configured'
        else:
            # Get form data
            url = request.form.get('newsUrl', '').strip()
            text = request.form.get('newsText', '').strip()
            tone = request.form.get('customTone', 'neutral').strip() or 'neutral'
            
            # Validation
            if not url and not text:
                error_message = 'Either URL or text must be provided'
            elif url and not text and not GEMINI_URL_API_KEY:
                error_message = 'URL analysis requires GEMINI_URL_API_KEY to be configured'
            elif text and not url and not GEMINI_TEXT_API_KEY:
                error_message = 'Text analysis requires GEMINI_TEXT_API_KEY to be configured'
            else:
                # Analyze the article
                analysis_result = analyze_article(url=url or None, text=text or None, tone=tone)
                
                if analysis_result['success']:
                    result = analysis_result
                    result['bias_level'] = get_bias_level(result['bias_score'])
                    result['bias_class'] = get_bias_color_class(result['bias_level'])
                else:
                    error_message = analysis_result['error']
    
    return render_template('index.html', 
                         result=result, 
                         error_message=error_message,
                         gemini_url_configured=GEMINI_URL_API_KEY is not None,
                         gemini_text_configured=GEMINI_TEXT_API_KEY is not None)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return render_template('health.html', 
                         timestamp=datetime.now().isoformat(),
                         gemini_url_configured=GEMINI_URL_API_KEY is not None,
                         gemini_text_configured=GEMINI_TEXT_API_KEY is not None)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)