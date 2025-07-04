"""Thread extractor for reconstructing Twitter threads."""

import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import asyncio

from ..utils.logger import get_logger, log_execution_time
from .tweet_extractor import TweetExtractor

logger = get_logger(__name__)


class ThreadExtractor:
    """Extract and reconstruct Twitter threads from bookmarks."""
    
    def __init__(self, tweet_extractor: Optional[TweetExtractor] = None):
        """
        Initialize thread extractor.
        
        Args:
            tweet_extractor: Tweet extractor instance to use
        """
        self.tweet_extractor = tweet_extractor or TweetExtractor()
        self.thread_cache: Dict[str, List[Dict[str, Any]]] = {}
        
    @log_execution_time
    async def extract_threads(
        self,
        tweets: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract threads from a list of tweets.
        
        Args:
            tweets: List of tweet data
            
        Returns:
            Tuple of (threads, standalone_tweets)
        """
        logger.info(f"Extracting threads from {len(tweets)} tweets")
        
        # Group tweets by author
        tweets_by_author = self._group_by_author(tweets)
        
        threads = []
        standalone_tweets = []
        
        for author, author_tweets in tweets_by_author.items():
            # Sort by creation time if available
            sorted_tweets = self._sort_tweets(author_tweets)
            
            # Identify potential threads
            author_threads = await self._identify_threads(sorted_tweets)
            
            for thread in author_threads:
                if len(thread) > 1:
                    thread_data = self._create_thread_data(thread)
                    threads.append(thread_data)
                else:
                    standalone_tweets.extend(thread)
        
        logger.info(f"Found {len(threads)} threads and {len(standalone_tweets)} standalone tweets")
        return threads, standalone_tweets
    
    def _group_by_author(self, tweets: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group tweets by author."""
        grouped = defaultdict(list)
        
        for tweet in tweets:
            author = tweet.get('author', 'unknown')
            grouped[author].append(tweet)
        
        return dict(grouped)
    
    def _sort_tweets(self, tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort tweets by creation time."""
        def get_timestamp(tweet: Dict[str, Any]) -> float:
            created_at = tweet.get('created_at')
            if not created_at:
                return 0
            
            try:
                # Try parsing different date formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                    try:
                        dt = datetime.strptime(created_at, fmt)
                        return dt.timestamp()
                    except ValueError:
                        continue
                
                # If all fail, try to extract from tweet ID (snowflake)
                tweet_id = tweet.get('id')
                if tweet_id and tweet_id.isdigit():
                    # Twitter snowflake epoch: 2010-11-04
                    return int(tweet_id) >> 22
                    
            except Exception:
                pass
            
            return 0
        
        return sorted(tweets, key=get_timestamp)
    
    async def _identify_threads(self, tweets: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Identify threads from a list of tweets.
        
        Args:
            tweets: List of tweets from same author
            
        Returns:
            List of thread groups
        """
        threads = []
        used_tweets = set()
        
        for i, tweet in enumerate(tweets):
            if tweet['id'] in used_tweets:
                continue
            
            thread = await self._build_thread(tweet, tweets[i:], used_tweets)
            threads.append(thread)
        
        return threads
    
    async def _build_thread(
        self,
        start_tweet: Dict[str, Any],
        remaining_tweets: List[Dict[str, Any]],
        used_tweets: set
    ) -> List[Dict[str, Any]]:
        """
        Build a thread starting from a tweet.
        
        Args:
            start_tweet: Starting tweet
            remaining_tweets: Remaining tweets to check
            used_tweets: Set of already used tweet IDs
            
        Returns:
            List of tweets in thread order
        """
        thread = [start_tweet]
        used_tweets.add(start_tweet['id'])
        
        # Check if this is a thread start
        if not self._is_thread_indicator(start_tweet):
            return thread
        
        # Look for continuation tweets
        current_number = self._extract_thread_number(start_tweet.get('content', ''))
        
        for tweet in remaining_tweets[1:]:  # Skip the start tweet
            if tweet['id'] in used_tweets:
                continue
            
            # Check if this tweet continues the thread
            if self._is_thread_continuation(tweet, thread[-1], current_number):
                thread.append(tweet)
                used_tweets.add(tweet['id'])
                current_number = self._extract_thread_number(tweet.get('content', ''))
        
        return thread
    
    def _is_thread_indicator(self, tweet: Dict[str, Any]) -> bool:
        """Check if tweet indicates start of a thread."""
        content = tweet.get('content', '').lower()
        metadata = tweet.get('metadata', {})
        
        indicators = [
            '🧵',
            'thread',
            'a thread',
            '1/',
            '1.',
            '[thread]',
            'thread:',
        ]
        
        # Check content
        if any(indicator in content for indicator in indicators):
            return True
        
        # Check if categorized as thread start
        if metadata.get('tweet_type') == 'thread_start':
            return True
        
        return False
    
    def _is_thread_continuation(
        self,
        tweet: Dict[str, Any],
        previous_tweet: Dict[str, Any],
        expected_number: Optional[int]
    ) -> bool:
        """Check if tweet continues a thread."""
        content = tweet.get('content', '')
        
        # Check for explicit numbering
        tweet_number = self._extract_thread_number(content)
        if tweet_number and expected_number:
            return tweet_number == expected_number + 1
        
        # Check for reply to self
        if self._is_self_reply(tweet, previous_tweet):
            return True
        
        # Check for continuation patterns
        continuation_patterns = [
            r'^\d+[\.\/]',  # Starts with number
            r'^continuing',
            r'^also',
            r'^furthermore',
            r'^additionally',
        ]
        
        return any(re.match(pattern, content.lower()) for pattern in continuation_patterns)
    
    def _extract_thread_number(self, content: str) -> Optional[int]:
        """Extract thread number from content."""
        patterns = [
            r'^(\d+)[\.\/]',  # 1. or 1/
            r'^(\d+)\)',       # 1)
            r'\[(\d+)\]',      # [1]
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass
        
        return None
    
    def _is_self_reply(self, tweet: Dict[str, Any], previous_tweet: Dict[str, Any]) -> bool:
        """Check if tweet is a reply to self."""
        # Check if same author
        if tweet.get('author') != previous_tweet.get('author'):
            return False
        
        # Check metadata for reply info
        metadata = tweet.get('metadata', {})
        if metadata.get('in_reply_to_user') == tweet.get('author'):
            return True
        
        # Check if content starts with self-mention
        content = tweet.get('content', '')
        author = tweet.get('author', '')
        if content.startswith(f'@{author}'):
            return True
        
        return False
    
    def _create_thread_data(self, thread_tweets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create consolidated thread data.
        
        Args:
            thread_tweets: List of tweets in thread
            
        Returns:
            Thread data structure
        """
        first_tweet = thread_tweets[0]
        last_tweet = thread_tweets[-1]
        
        # Combine content
        full_content = '\n\n---\n\n'.join(
            f"{i+1}. {tweet.get('content', '')}"
            for i, tweet in enumerate(thread_tweets)
        )
        
        # Combine metadata
        all_urls = []
        all_hashtags = []
        all_mentions = []
        has_media = False
        
        for tweet in thread_tweets:
            metadata = tweet.get('metadata', {})
            all_urls.extend(metadata.get('urls', []))
            all_hashtags.extend(metadata.get('hashtags', []))
            all_mentions.extend(metadata.get('mentioned_users', []))
            has_media = has_media or metadata.get('has_media', False)
        
        # Remove duplicates while preserving order
        all_urls = list(dict.fromkeys(all_urls))
        all_hashtags = list(dict.fromkeys(all_hashtags))
        all_mentions = list(dict.fromkeys(all_mentions))
        
        thread_data = {
            'id': f"thread_{first_tweet['id']}",
            'type': 'thread',
            'author': first_tweet.get('author'),
            'url': first_tweet.get('url'),
            'created_at': first_tweet.get('created_at'),
            'updated_at': last_tweet.get('created_at'),
            'tweet_count': len(thread_tweets),
            'content': full_content,
            'tweets': thread_tweets,
            'metadata': {
                'thread_length': len(thread_tweets),
                'urls': all_urls,
                'hashtags': all_hashtags,
                'mentioned_users': all_mentions,
                'has_media': has_media,
                'first_tweet_id': first_tweet['id'],
                'last_tweet_id': last_tweet['id'],
                'reading_time': self._estimate_thread_reading_time(full_content),
            }
        }
        
        return thread_data
    
    def _estimate_thread_reading_time(self, content: str) -> int:
        """Estimate reading time for thread in minutes."""
        words = len(content.split())
        # Slightly slower reading speed for threads due to context switching
        return max(1, int(words / 180 + 0.5))
    
    def analyze_thread_structure(self, thread: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the structure and flow of a thread.
        
        Args:
            thread: Thread data
            
        Returns:
            Analysis results
        """
        tweets = thread.get('tweets', [])
        
        analysis = {
            'total_tweets': len(tweets),
            'has_numbering': False,
            'has_conclusion': False,
            'has_call_to_action': False,
            'topics': [],
            'structure_type': 'linear',  # linear, branching, mixed
            'engagement_pattern': [],
        }
        
        # Check for numbering
        numbered_tweets = sum(
            1 for tweet in tweets
            if self._extract_thread_number(tweet.get('content', ''))
        )
        analysis['has_numbering'] = numbered_tweets > len(tweets) / 2
        
        # Check for conclusion
        last_content = tweets[-1].get('content', '').lower() if tweets else ''
        conclusion_indicators = ['conclusion', 'summary', 'tldr', 'in summary', 'to sum up']
        analysis['has_conclusion'] = any(ind in last_content for ind in conclusion_indicators)
        
        # Check for call to action
        cta_indicators = ['follow', 'subscribe', 'share', 'retweet', 'like', 'comment']
        analysis['has_call_to_action'] = any(ind in last_content for ind in cta_indicators)
        
        return analysis
    
    def extract_thread_insights(self, thread: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key insights from a thread.
        
        Args:
            thread: Thread data
            
        Returns:
            Insights dictionary
        """
        content = thread.get('content', '')
        tweets = thread.get('tweets', [])
        
        insights = {
            'main_points': [],
            'questions_raised': [],
            'resources_mentioned': [],
            'action_items': [],
        }
        
        # Extract questions
        questions = re.findall(r'[^.!?]*\?', content)
        insights['questions_raised'] = [q.strip() for q in questions if len(q.strip()) > 10]
        
        # Extract URLs as resources
        metadata = thread.get('metadata', {})
        urls = metadata.get('urls', [])
        insights['resources_mentioned'] = [
            url for url in urls
            if not any(domain in url for domain in ['twitter.com', 'x.com', 't.co'])
        ]
        
        # Extract action items (simple heuristic)
        action_patterns = [
            r'(?:you should|try to|make sure to|don\'t forget to)\s+([^.!?]+)',
            r'(?:step \d+:|first,|second,|finally,)\s+([^.!?]+)',
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, content.lower())
            insights['action_items'].extend([m.strip() for m in matches if len(m.strip()) > 10])
        
        return insights