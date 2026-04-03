import asyncio
import aiohttp
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from diskcache import Cache
from pathlib import Path

cache = Cache(Path(__file__).parent.parent / "cache")
cache.expire = 3600

class AsyncSteamParser:
    def __init__(self, max_concurrent=10):
        self.ua = UserAgent()
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
        
    async def _get(self, url: str, params: dict = None) -> Optional[str]:
        async with self.semaphore:
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            }
            
            try:
                async with self.session.get(url, params=params, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
            except Exception:
                return None
    
    async def get_sale_games(self, max_pages: int = 3) -> List[Dict]:
        tasks = [self._parse_sale_page(page) for page in range(1, max_pages + 1)]
        results = await asyncio.gather(*tasks)
        
        all_games = []
        for games in results:
            if games:
                all_games.extend(games)
        return all_games
    
    async def _parse_sale_page(self, page: int) -> List[Dict]:
        url = "https://store.steampowered.com/search/"
        params = {
            'specials': '1',
            'page': page,
            'cc': 'ru',
            'l': 'russian',
            'category1': '998',
        }
        
        html = await self._get(url, params)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        game_blocks = soup.select('a.search_result_row')
        
        games = []
        for block in game_blocks:
            game = self._parse_game_block(block)
            if game:
                games.append(game)
        
        print(f"  📄 Страница {page}: {len(games)} игр")
        return games
    
    def _parse_game_block(self, block) -> Optional[Dict]:
        try:
            href = block.get('href', '')
            app_id_match = re.search(r'app/(\d+)', href)
            if not app_id_match:
                return None
            app_id = int(app_id_match.group(1))
            
            title_elem = block.select_one('.title')
            name = title_elem.text.strip() if title_elem else 'Unknown'
            
            discount_elem = block.select_one('.discount_pct')
            discount = 0
            if discount_elem:
                discount_text = discount_elem.text.strip()
                discount_match = re.search(r'(\d+)', discount_text)
                if discount_match:
                    discount = int(discount_match.group(1))
            
            price_elem = block.select_one('.discount_final_price')
            price = 0
            if price_elem:
                price_text = price_elem.text.strip()
                price_text = re.sub(r'[^\d]', '', price_text)
                if price_text:
                    price = int(price_text)
            
            return {
                'app_id': app_id,
                'name': name,
                'discount': discount,
                'price': price,
                'url': f"https://store.steampowered.com/app/{app_id}/"
            }
        except:
            return None
    
    async def get_game_details(self, app_id: int) -> Optional[Dict]:
        cache_key = f"game_{app_id}"
        if cache_key in cache:
            return cache[cache_key]
        
        url = f"https://store.steampowered.com/app/{app_id}/"
        html = await self._get(url)
        
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'lxml')
        
        genres = []
        genre_elems = soup.select('.glance_tags a')
        for genre in genre_elems:
            genres.append({'description': genre.text.strip()})
        
        developers = []
        dev_elems = soup.select('.dev_row a')
        for dev in dev_elems:
            developers.append(dev.text.strip())
        
        rating = 0
        rating_meta = soup.find('meta', {'itemprop': 'ratingValue'})
        if rating_meta:
            try:
                rating = int(float(rating_meta.get('content', 0)))
            except:
                pass
        
        if rating == 0:
            metacritic_link = soup.select_one('.metascore_anchor')
            if metacritic_link:
                score_text = metacritic_link.text.strip()
                score_match = re.search(r'(\d+)', score_text)
                if score_match:
                    rating = int(score_match.group(1))
        
        result = {
            'app_id': app_id,
            'genres': genres,
            'developers': developers,
            'rating_percent': rating,
        }
        
        cache[cache_key] = result
        return result
    
    async def enrich_games_with_details(self, games: List[Dict]) -> List[Dict]:
        tasks = [self.get_game_details(game['app_id']) for game in games]
        details_list = await asyncio.gather(*tasks)
        
        enriched = []
        for game, details in zip(games, details_list):
            if details:
                game.update(details)
                enriched.append(game)
        
        print(f"  ✅ Загружено деталей для {len(enriched)} игр")
        return enriched
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        await self.close()