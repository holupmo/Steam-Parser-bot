from typing import List, Dict, Optional

class GameFilter:
    def __init__(
        self,
        min_discount: int = 70,
        min_rating: int = 0,
        max_price: Optional[int] = None,
        genres: Optional[List[str]] = None,
    ):
        self.min_discount = min_discount
        self.min_rating = min_rating
        self.max_price = max_price
        self.genres = [g.lower() for g in (genres or [])]
    
    def apply(self, game: Dict) -> bool:
        if game.get('discount', 0) < self.min_discount:
            return False
        
        if self.min_rating > 0:
            rating = game.get('rating_percent', 0)
            if rating < self.min_rating:
                return False
        
        price = game.get('price', 0)
        if self.max_price and price > self.max_price:
            return False
        
        if self.genres and 'genres' in game:
            game_genres = [g.get('description', '').lower() for g in game.get('genres', [])]
            if not any(genre in game_genres for genre in self.genres):
                return False
        
        return True
    
    def filter_batch(self, games: List[Dict]) -> List[Dict]:
        filtered = [g for g in games if self.apply(g)]
        removed = len(games) - len(filtered)
        if removed > 0:
            print(f"  📊 Отфильтровано {removed} игр (осталось {len(filtered)})")
        return filtered