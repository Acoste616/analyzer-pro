import re
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..utils.validation import validate_url
from .tweet_extractor import TweetExtractor


class ThreadExtractor:
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.tweet_extractor = TweetExtractor()
        
        # Configuration
        self.twitter_config = self.settings.extractors.get('twitter', {})
        self.max_thread_length = 50  # Maximum number of tweets to extract in a thread
        self.delay_between_requests = 1.0  # Delay between requests to avoid rate limiting
    
    async def extract(self, bookmark_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract Twitter thread content from URL or existing data
        
        Args:
            bookmark_data: Dictionary containing thread URL and any existing data
            
        Returns:
            Dictionary with extracted thread data
        """
        url = bookmark_data.get('url', '')
        if not validate_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        # Check if this is a Twitter/X URL
        if not self._is_twitter_url(url):
            raise ValueError(f"Not a Twitter URL: {url}")
        
        try:
            # Extract the main tweet first
            main_tweet_data = await self._extract_main_tweet(url)
            
            # Check if this tweet is part of a thread
            if not self._is_thread_tweet(main_tweet_data):
                # If it's not a thread, return as a single tweet
                return self._format_single_tweet_as_thread(main_tweet_data)
            
            # Extract the full thread
            thread_data = await self._extract_full_thread(url, main_tweet_data)
            
            return thread_data
            
        except Exception as e:
            self.logger.error(f"Error extracting thread from {url}: {str(e)}")
            # Return basic data structure
            return {
                'title': f"Twitter Thread",
                'content': bookmark_data.get('content', ''),
                'author': bookmark_data.get('author', ''),
                'metadata': {
                    'thread_length': 1,
                    'url': url,
                    'extraction_method': 'fallback',
                    'error': str(e)
                }
            }
    
    def _is_twitter_url(self, url: str) -> bool:
        """Check if URL is from Twitter/X"""
        parsed = urlparse(url)
        return parsed.netloc.lower() in ['twitter.com', 'x.com', 'www.twitter.com', 'www.x.com']
    
    async def _extract_main_tweet(self, url: str) -> Dict[str, Any]:
        """Extract the main tweet data"""
        async with self.tweet_extractor:
            return await self.tweet_extractor.extract({'url': url})
    
    def _is_thread_tweet(self, tweet_data: Dict[str, Any]) -> bool:
        """Check if a tweet is part of a thread"""
        content = tweet_data.get('content', '')
        metadata = tweet_data.get('metadata', {})
        
        # Check for thread indicators
        thread_indicators = [
            'thread',
            '1/',
            '1/n',
            '👇',
            'see below',
            'continued',
            'part 1',
            'first tweet'
        ]
        
        content_lower = content.lower()
        
        # Check for thread indicators in content
        for indicator in thread_indicators:
            if indicator in content_lower:
                return True
        
        # Check if it's a reply to itself (common in threads)
        if self._is_self_reply(tweet_data):
            return True
        
        # Check for numbered patterns like "1/", "2/", etc.
        if re.search(r'\b\d+/\d*\b', content):
            return True
        
        return False
    
    def _is_self_reply(self, tweet_data: Dict[str, Any]) -> bool:
        """Check if the tweet is a reply to the same author"""
        content = tweet_data.get('content', '')
        author = tweet_data.get('author', '')
        
        # Check if it's replying to the same author
        if author and f"@{author}" in content:
            return True
        
        return False
    
    async def _extract_full_thread(self, main_url: str, main_tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the complete thread"""
        
        thread_tweets = [main_tweet_data]
        author = main_tweet_data.get('author', '')
        main_tweet_id = main_tweet_data.get('metadata', {}).get('tweet_id', '')
        
        if not author or not main_tweet_id:
            return self._format_thread_data(thread_tweets, main_url)
        
        try:
            # Try to find continuation tweets
            continuation_tweets = await self._find_continuation_tweets(author, main_tweet_id)
            thread_tweets.extend(continuation_tweets)
            
        except Exception as e:
            self.logger.warning(f"Could not extract full thread: {str(e)}")
        
        return self._format_thread_data(thread_tweets, main_url)
    
    async def _find_continuation_tweets(self, author: str, main_tweet_id: str) -> List[Dict[str, Any]]:
        """Find continuation tweets in the thread"""
        
        continuation_tweets = []
        
        # This is a simplified approach since we don't have access to Twitter API
        # In a real implementation, you would use Twitter API to find replies
        # or implement more sophisticated web scraping
        
        # For now, we'll try to construct potential URLs for continuation tweets
        # and check if they exist
        
        try:
            # Try to find tweets that are replies to the main tweet
            for i in range(2, min(self.max_thread_length + 1, 20)):  # Check up to 20 potential continuation tweets
                # This is a placeholder - in practice you'd need to use Twitter API
                # or more sophisticated scraping techniques
                
                # Wait to avoid rate limiting
                await asyncio.sleep(self.delay_between_requests)
                
                # For demonstration, we'll break after a few attempts
                if i > 5:
                    break
                
        except Exception as e:
            self.logger.warning(f"Error finding continuation tweets: {str(e)}")
        
        return continuation_tweets
    
    def _format_single_tweet_as_thread(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single tweet as a thread with length 1"""
        
        return {
            'title': f"Twitter Thread by {tweet_data.get('author', 'Unknown')}",
            'content': tweet_data.get('content', ''),
            'author': tweet_data.get('author', ''),
            'published_date': tweet_data.get('published_date'),
            'metadata': {
                'thread_length': 1,
                'tweets': [tweet_data],
                'content_type': 'thread',
                'original_url': tweet_data.get('metadata', {}).get('original_url', ''),
                'main_tweet_id': tweet_data.get('metadata', {}).get('tweet_id', ''),
                'extraction_method': 'single_tweet'
            }
        }
    
    def _format_thread_data(self, tweets: List[Dict[str, Any]], original_url: str) -> Dict[str, Any]:
        """Format multiple tweets into a thread structure"""
        
        if not tweets:
            raise ValueError("No tweets provided for thread formatting")
        
        main_tweet = tweets[0]
        author = main_tweet.get('author', 'Unknown')
        
        # Combine all tweet content
        combined_content = []
        for i, tweet in enumerate(tweets, 1):
            content = tweet.get('content', '')
            if content:
                if len(tweets) > 1:
                    combined_content.append(f"{i}. {content}")
                else:
                    combined_content.append(content)
        
        full_content = '\n\n'.join(combined_content)
        
        # Create title
        if len(tweets) > 1:
            title = f"Twitter Thread by {author} ({len(tweets)} tweets)"
        else:
            title = f"Tweet by {author}"
        
        # Aggregate metadata
        thread_metadata = {
            'thread_length': len(tweets),
            'tweets': tweets,
            'content_type': 'thread',
            'original_url': original_url,
            'main_tweet_id': main_tweet.get('metadata', {}).get('tweet_id', ''),
            'author': author,
            'extraction_method': 'thread_extraction',
            'extracted_at': datetime.now().isoformat()
        }
        
        # Aggregate engagement metrics
        total_engagement = {
            'total_replies': 0,
            'total_retweets': 0,
            'total_likes': 0
        }
        
        all_hashtags = set()
        all_mentions = set()
        
        for tweet in tweets:
            metadata = tweet.get('metadata', {})
            engagement = metadata.get('engagement', {})
            
            total_engagement['total_replies'] += engagement.get('replies', 0)
            total_engagement['total_retweets'] += engagement.get('retweets', 0)
            total_engagement['total_likes'] += engagement.get('likes', 0)
            
            # Collect hashtags and mentions
            hashtags = metadata.get('hashtags', [])
            mentions = metadata.get('mentions', [])
            
            all_hashtags.update(hashtags)
            all_mentions.update(mentions)
        
        thread_metadata['total_engagement'] = total_engagement
        
        if all_hashtags:
            thread_metadata['hashtags'] = list(all_hashtags)
        
        if all_mentions:
            thread_metadata['mentions'] = list(all_mentions)
        
        return {
            'title': title,
            'content': full_content,
            'author': author,
            'published_date': main_tweet.get('published_date'),
            'metadata': thread_metadata
        }
    
    def get_thread_summary(self, thread_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of the thread"""
        
        metadata = thread_data.get('metadata', {})
        tweets = metadata.get('tweets', [])
        
        if not tweets:
            return {}
        
        # Calculate statistics
        total_chars = sum(len(tweet.get('content', '')) for tweet in tweets)
        avg_chars_per_tweet = total_chars / len(tweets) if tweets else 0
        
        # Find tweet with most engagement
        most_engaged_tweet = None
        max_engagement = 0
        
        for tweet in tweets:
            engagement = tweet.get('metadata', {}).get('engagement', {})
            total_eng = sum(engagement.values()) if engagement else 0
            
            if total_eng > max_engagement:
                max_engagement = total_eng
                most_engaged_tweet = tweet
        
        return {
            'thread_length': metadata.get('thread_length', 0),
            'total_characters': total_chars,
            'average_characters_per_tweet': round(avg_chars_per_tweet, 1),
            'total_engagement': metadata.get('total_engagement', {}),
            'most_engaged_tweet': most_engaged_tweet,
            'hashtags_count': len(metadata.get('hashtags', [])),
            'mentions_count': len(metadata.get('mentions', [])),
            'estimated_reading_time': round(total_chars / 1000, 1)  # Rough estimate in minutes
        }
    
    def extract_key_points(self, thread_data: Dict[str, Any]) -> List[str]:
        """Extract key points from the thread"""
        
        content = thread_data.get('content', '')
        if not content:
            return []
        
        # Split by numbered points
        points = re.split(r'\n\n\d+\.\s*', content)
        key_points = []
        
        for point in points:
            point = point.strip()
            if point and len(point) > 20:  # Filter out very short points
                # Take first sentence of each point as key point
                sentences = point.split('.')
                if sentences:
                    key_point = sentences[0].strip()
                    if key_point:
                        key_points.append(key_point)
        
        return key_points[:10]  # Return top 10 key points
    
    def get_thread_topics(self, thread_data: Dict[str, Any]) -> List[str]:
        """Extract topics from the thread"""
        
        topics = set()
        
        # Get hashtags as topics
        metadata = thread_data.get('metadata', {})
        hashtags = metadata.get('hashtags', [])
        topics.update(hashtags)
        
        # Extract topics from content using keyword analysis
        content = thread_data.get('content', '').lower()
        
        # Common topic keywords
        topic_keywords = {
            'technology': ['tech', 'software', 'programming', 'development', 'coding', 'ai', 'ml'],
            'business': ['startup', 'business', 'entrepreneur', 'marketing', 'sales', 'strategy'],
            'finance': ['money', 'finance', 'investment', 'crypto', 'stocks', 'trading'],
            'career': ['career', 'job', 'work', 'professional', 'skills', 'learning'],
            'productivity': ['productivity', 'efficiency', 'time', 'management', 'workflow'],
            'design': ['design', 'ui', 'ux', 'visual', 'creative', 'art'],
            'health': ['health', 'fitness', 'wellness', 'mental', 'exercise']
        }
        
        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword in content:
                    topics.add(topic)
                    break
        
        return list(topics)
    
    def is_complete_thread(self, thread_data: Dict[str, Any]) -> bool:
        """Check if the thread appears to be complete"""
        
        metadata = thread_data.get('metadata', {})
        tweets = metadata.get('tweets', [])
        
        if not tweets:
            return False
        
        # Check if the last tweet has continuation indicators
        last_tweet = tweets[-1]
        last_content = last_tweet.get('content', '').lower()
        
        continuation_indicators = [
            'continued',
            'more in next tweet',
            'thread continues',
            '...',
            'to be continued'
        ]
        
        for indicator in continuation_indicators:
            if indicator in last_content:
                return False
        
        return True
    
    def get_thread_structure(self, thread_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the structure of the thread"""
        
        metadata = thread_data.get('metadata', {})
        tweets = metadata.get('tweets', [])
        
        structure = {
            'total_tweets': len(tweets),
            'has_introduction': False,
            'has_conclusion': False,
            'has_numbered_points': False,
            'has_call_to_action': False
        }
        
        if not tweets:
            return structure
        
        # Check first tweet for introduction
        first_content = tweets[0].get('content', '').lower()
        intro_indicators = ['thread', 'today i', 'let me explain', 'here\'s how']
        structure['has_introduction'] = any(indicator in first_content for indicator in intro_indicators)
        
        # Check last tweet for conclusion
        if len(tweets) > 1:
            last_content = tweets[-1].get('content', '').lower()
            conclusion_indicators = ['in conclusion', 'to summarize', 'finally', 'that\'s it']
            structure['has_conclusion'] = any(indicator in last_content for indicator in conclusion_indicators)
        
        # Check for numbered points
        full_content = thread_data.get('content', '')
        structure['has_numbered_points'] = bool(re.search(r'\d+\.\s', full_content))
        
        # Check for call to action
        cta_indicators = ['follow me', 'retweet', 'like if', 'share this', 'subscribe']
        structure['has_call_to_action'] = any(
            indicator in tweet.get('content', '').lower() 
            for tweet in tweets 
            for indicator in cta_indicators
        )
        
        return structure