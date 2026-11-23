"""
LearnSphere - Base Repository (Tier 3)
Abstracts common MongoDB operations with query sanitization,
safe ObjectId conversion, and high-performance pagination.
"""

from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.collection import Collection
from database.connection import get_collection
from core.validation import assert_no_mongo_operators, ValidationError


class BaseRepository:
    """
    Base Repository implementing Data Access Object pattern.
    Provides schema type boundary validation and protection against NoSQL injection.
    """

    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self._collection: Optional[Collection] = None

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection(self.collection_name)
        return self._collection

    @staticmethod
    def to_object_id(id_str: str) -> Optional[ObjectId]:
        """Safely parses string to BSON ObjectId."""
        try:
            if isinstance(id_str, ObjectId):
                return id_str
            return ObjectId(str(id_str))
        except Exception:
            return None

    @staticmethod
    def format_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Converts BSON ObjectId to string for JSON/template compatibility."""
        if not doc:
            return None
        res = dict(doc)
        if "_id" in res and isinstance(res["_id"], ObjectId):
            res["id"] = str(res["_id"])
            res["_id"] = str(res["_id"])
        return res

    @staticmethod
    def format_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Formats list of documents."""
        return [BaseRepository.format_doc(d) for d in docs if d]

    @staticmethod
    def sanitize_query(query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitizes search query to prevent NoSQL operator injection in user inputs.
        Disallows dangerous operators from untrusted input keys.
        """
        if not query or not isinstance(query, dict):
            return {}

        clean_query = {}
        for key, val in query.items():
            if not isinstance(key, str):
                continue
            # Allow legitimate root query combinators ($or, $and, $text, $in)
            if key.startswith("$") and key not in ["$or", "$and", "$text", "$in", "$nin"]:
                continue

            # If value is a nested dictionary, verify no unauthorized operators
            if isinstance(val, dict):
                clean_sub = {}
                for sub_k, sub_v in val.items():
                    if isinstance(sub_k, str) and sub_k.startswith("$") and sub_k not in [
                        "$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin", "$regex", "$options", "$exists"
                    ]:
                        continue
                    clean_sub[sub_k] = sub_v
                clean_query[key] = clean_sub
            else:
                clean_query[key] = val

        return clean_query

    def find_one(self, query: Dict[str, Any], projection: Optional[Dict[str, int]] = None) -> Optional[Dict[str, Any]]:
        clean = self.sanitize_query(query)
        doc = self.collection.find_one(clean, projection)
        return self.format_doc(doc)

    def find_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        oid = self.to_object_id(doc_id)
        if not oid:
            return None
        return self.find_one({"_id": oid})

    def find_many(
        self,
        query: Dict[str, Any] = None,
        sort: Optional[List[tuple]] = None,
        skip: int = 0,
        limit: int = 50,
        projection: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        clean = self.sanitize_query(query or {})
        cursor = self.collection.find(clean, projection)
        if sort:
            cursor = cursor.sort(sort)
        if skip > 0:
            cursor = cursor.skip(skip)
        if limit > 0:
            cursor = cursor.limit(limit)
        return self.format_docs(list(cursor))

    def count(self, query: Dict[str, Any] = None) -> int:
        clean = self.sanitize_query(query or {})
        return self.collection.count_documents(clean)

    def insert_one(self, data: Dict[str, Any]) -> str:
        doc = dict(data)
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def update_one(self, query: Dict[str, Any], update_data: Dict[str, Any]) -> bool:
        clean_query = self.sanitize_query(query)
        if not any(k.startswith("$") for k in update_data.keys()):
            update_body = {"$set": update_data}
        else:
            update_body = update_data
        result = self.collection.update_one(clean_query, update_body)
        return result.modified_count > 0 or result.matched_count > 0

    def delete_one(self, query: Dict[str, Any]) -> bool:
        clean = self.sanitize_query(query)
        result = self.collection.delete_one(clean)
        return result.deleted_count > 0

    def paginate(
        self,
        query: Dict[str, Any] = None,
        page: int = 1,
        per_page: int = 12,
        sort: Optional[List[tuple]] = None
    ) -> Dict[str, Any]:
        """Provides fast, memory-efficient pagination."""
        page = max(1, page)
        per_page = max(1, min(per_page, 100))
        skip = (page - 1) * per_page

        total = self.count(query)
        items = self.find_many(query, sort=sort, skip=skip, limit=per_page)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
