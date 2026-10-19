import json
from datetime import datetime

with open('prototype/reelshort_next_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

info = d['fallback']['/api/ms/hall/webInfo']
banners = info.get('banners', [])

books = []
for b in banners:
    jp = b.get('jump_param', {})
    title = jp.get('book_title') or b.get('title')
    book_id = jp.get('book_id')
    count = jp.get('chapter_count')
    books.append({
        'title': title,
        'book_id': book_id,
        'count': count,
        'source': 'banner'
    })

print(f"Total banner books: {len(books)}")
for b in books:
    print(f"  {b['title']} (ID: {b['book_id']}, Chapters: {b['count']})")
