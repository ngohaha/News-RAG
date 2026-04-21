import time
from .retriever import Retriever
from .generator import generator_registry
from .schemas import SearchHit, GeneratorResponse
from .logger_setup import logger
from typing import List
from .config import settings

class Pipeline:
    """A simple pipeline to execute a sequence of steps with timing."""
    def __init__(self):
        self.retriever = Retriever()
        self.settings = settings

    def ask(self, query: str, model:str=None) -> GeneratorResponse:
        """Run the pipeline with the given query and return the result."""
        if not model:
            logger.warning("[Engine] No specific model provided. Using default generator.")
            generator = generator_registry.get_generator("default")
        else:
            logger.info(f"[Engine] Using model '{model}' for generation.")
            generator= generator_registry.get_generator(model)

        logger.info(f"[Engine] Received query: '{query}'. Starting pipeline execution...")

        try:
            start_time = time.time()
            # Step 1: Retrieval
            sources: List[SearchHit] = self.retriever.search(query)

            # Step 2: Generation
            if not sources:
                logger.warning("[Engine] No relevant sources found for the given query.")
                return GeneratorResponse(
                    query=query,
                    summary="Không tìm thấy nguồn tin nào liên quan đến câu hỏi của bạn.",
                    results=[],
                    total=0,
                    duration_ms=(time.time() - start_time) * 1000
                )
            else:
                answer = generator.generate(query, sources)
                duration_ms = (time.time() - start_time) * 1000
                return GeneratorResponse(
                    query=query,
                    summary=answer,
                    results=sources,
                    total=len(sources),
                    duration_ms=round(duration_ms, 2)
                )
        except Exception as e:
            logger.exception("Pipeline execution failed")
            return GeneratorResponse(
                query=query,
                summary=None,
                results=[],
                total=0,
                duration_ms=0.0
            )
