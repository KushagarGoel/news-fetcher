
from src.storage.vector_store import VectorStore
from src.models import Category

store = VectorStore()

# Get stats
print('=== Collection Stats ===')
stats = store.get_collection_stats()
for cat, count in stats.items():
    print(f'{cat}: {count} articles')

# View tech articles
print('\n=== Tech Articles ===')
collection = store.get_collection(Category.COMPETITOR)
if collection:
    results = collection.get(limit=33)
    for i, doc_id in enumerate(results['ids']):
        meta = results['metadatas'][i]
        print(meta)
        print(f'{i+1}. {meta["title"]}')
        print(f'   URL: {meta["url"]}')
        print(f'   Tags: {meta.get("tags", "")}')
        print()
