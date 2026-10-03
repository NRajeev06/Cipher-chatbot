import logging
from typing import Dict, Any, List
from core.config import settings

logger = logging.getLogger("cipher.search")

def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Executes a real-time web search using the Tavily Search API.
    Returns a dictionary with query, summarized answer (if available),
    extracted result snippets, and sources list (titles + urls).
    """
    tavily_key = (settings.TAVILY_API_KEY or "").strip().strip('"').strip("'")
    if not tavily_key:
        logger.warning(f"⚠️ [TAVILY SEARCH] Query '{query}' skipped: TAVILY_API_KEY is not configured.")
        return {
            "error": "Tavily API key is not configured.",
            "query": query,
            "results": [],
            "sources": []
        }

    try:
        logger.info(f"🌐 [TAVILY SEARCH] Initiating live web search: '{query}' (max_results={max_results})")
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=True
        )

        results: List[Dict[str, str]] = []
        sources: List[Dict[str, str]] = []

        raw_results = response.get("results", [])
        for item in raw_results:
            title = (item.get("title") or "Web Result").strip()
            url = (item.get("url") or "").strip()
            content = (item.get("content") or "").strip()

            results.append({
                "title": title,
                "url": url,
                "content": content
            })

            if url:
                sources.append({
                    "title": title,
                    "url": url
                })

        logger.info(f"✅ [TAVILY SEARCH] Completed for '{query}': {len(results)} results found, has_answer={bool(response.get('answer'))}")
        return {
            "query": query,
            "answer": response.get("answer", ""),
            "results": results,
            "sources": sources
        }

    except Exception as e:
        logger.error(f"❌ [TAVILY SEARCH] Execution failed for '{query}': {e}")
        return {
            "error": f"Tavily search failed: {str(e)}",
            "query": query,
            "results": [],
            "sources": []
        }
