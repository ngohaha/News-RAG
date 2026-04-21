import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
from .config import settings

logger = logging.getLogger(__name__)

def ensure_qdrant_collection_exists():
    """Ensure that the Qdrant collection exists, creating it if necessary."""
    client = QdrantClient(url=settings.search.qdrant_url)
    collection_name = settings.search.collection_name
    vector_size = settings.search.embedding_size

    try:
        if not client.client_exists(collection_name):
            logger.info(f"Collection'{collection_name}'does not exist. Initializing...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, 
                    distance=models.Distance.COSINE)
            ),
            sparse_config={
                "text_sparse": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False)
                )
            }

            logger.info(f"Collection '{collection_name}' created successfully.")

    except Exception as e:
        logger.error(f"Error ensuring collection exists: {e}")
        raise e

