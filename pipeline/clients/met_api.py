from typing import Any, Dict, List

import requests

BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


def search_object_ids(query: str, has_images: bool = True) -> List[int]:
    resp = requests.get(
        f"{BASE}/search", params={"q": query, "hasImages": has_images}, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("objectIDs") or []


def get_object(object_id: int) -> Dict[str, Any]:
    resp = requests.get(f"{BASE}/objects/{object_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def is_usable_candidate(obj: Dict[str, Any]) -> bool:
    return bool(
        obj.get("isPublicDomain")
        and obj.get("primaryImage")
        and (obj.get("title") or obj.get("objectName"))
    )


def summarize_for_llm(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Trim a full Met object record down to the fields worth giving the LLM."""
    return {
        "object_id": obj.get("objectID"),
        "title": obj.get("title"),
        "object_name": obj.get("objectName"),
        "culture": obj.get("culture"),
        "period": obj.get("period"),
        "dynasty": obj.get("dynasty"),
        "date": obj.get("objectDate"),
        "medium": obj.get("medium"),
        "dimensions": obj.get("dimensions"),
        "artist": obj.get("artistDisplayName"),
        "department": obj.get("department"),
        "credit_line": obj.get("creditLine"),
        "geography": {
            "type": obj.get("geographyType"),
            "country": obj.get("country"),
            "region": obj.get("region"),
            "city": obj.get("city"),
        },
        "tags": [t.get("term") for t in (obj.get("tags") or []) if t.get("term")],
        "primary_image": obj.get("primaryImage"),
        "additional_images": obj.get("additionalImages") or [],
        "object_url": obj.get("objectURL"),
    }
