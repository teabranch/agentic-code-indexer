import asyncio
import os
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass
import logging
from pathlib import Path
import json
import aiohttp
import torch
from transformers import AutoTokenizer, AutoModel
from anthropic import AsyncAnthropic
import numpy as np
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    text: str
    embedding: List[float]
    model_name: str
    dimension: int

@dataclass
class SummaryResult:
    """Result of a summary generation operation."""
    original_text: str
    summary: str
    model_name: str
    token_count: Optional[int] = None

class EmbeddingGenerator:
    """
    Handles generation of embeddings using various models.
    Supports both local and API-based embedding generation.
    """
    
    def __init__(self, model_name: str = "jinaai/jina-embeddings-v2-base-code"):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the embedding model."""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(self.model_name, trust_remote_code=True)
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Model loaded successfully on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    async def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        try:
            # Tokenize and encode
            inputs = self.tokenizer(
                text, 
                padding=True, 
                truncation=True, 
                return_tensors='pt',
                max_length=512
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate embedding
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Use mean pooling of last hidden states
                embeddings = outputs.last_hidden_state.mean(dim=1)
                embeddings = embeddings.cpu().numpy().squeeze()
            
            return EmbeddingResult(
                text=text,
                embedding=embeddings.tolist(),
                model_name=self.model_name,
                dimension=len(embeddings)
            )
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str], batch_size: int = 32) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts in batches."""
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                # Tokenize batch
                inputs = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    return_tensors='pt',
                    max_length=512
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Generate embeddings
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    embeddings = outputs.last_hidden_state.mean(dim=1)
                    embeddings = embeddings.cpu().numpy()
                
                # Create results
                for j, text in enumerate(batch):
                    results.append(EmbeddingResult(
                        text=text,
                        embedding=embeddings[j].tolist(),
                        model_name=self.model_name,
                        dimension=len(embeddings[j])
                    ))
                    
            except Exception as e:
                logger.error(f"Error in batch embedding generation: {e}")
                # Add empty results for failed batch
                for text in batch:
                    results.append(EmbeddingResult(
                        text=text,
                        embedding=[],
                        model_name=self.model_name,
                        dimension=0
                    ))
        
        return results

class LLMSummarizer:
    """
    Handles summary generation using various LLM providers.
    Supports Anthropic Claude and other models.
    """
    
    def __init__(self, provider: str = "anthropic", model: str = "claude-3-sonnet-20240229"):
        self.provider = provider
        self.model = model
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the LLM client."""
        if self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            self.client = AsyncAnthropic(api_key=api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _create_summary_prompt(self, code_text: str, node_type: str, context: Optional[str] = None) -> str:
        """Create a prompt for code summarization."""
        base_prompt = f"""You are an expert code analyst. Analyze the following {node_type} and provide a concise, technical summary.

Focus on:
- Purpose and functionality
- Key methods/properties (for classes)
- Parameters and return types (for functions/methods)
- Important implementation details
- Dependencies and relationships

{node_type.title()}: {code_text}"""

        if context:
            base_prompt += f"\n\nContext: {context}"
        
        base_prompt += "\n\nProvide a clear, concise summary (2-4 sentences):"
        
        return base_prompt
    
    async def generate_summary(self, text: str, node_type: str = "code", context: Optional[str] = None) -> SummaryResult:
        """Generate summary for a single piece of code."""
        try:
            if self.provider == "anthropic":
                prompt = self._create_summary_prompt(text, node_type, context)
                
                message = await self.client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                summary = message.content[0].text
                token_count = message.usage.input_tokens + message.usage.output_tokens
                
                return SummaryResult(
                    original_text=text,
                    summary=summary,
                    model_name=self.model,
                    token_count=token_count
                )
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            # Return a fallback summary
            return SummaryResult(
                original_text=text,
                summary=f"Code {node_type} - summary generation failed",
                model_name=self.model,
                token_count=0
            )
    
    async def generate_summaries_batch(self, texts: List[str], node_types: List[str], contexts: Optional[List[str]] = None, max_concurrent: int = 5) -> List[SummaryResult]:
        """Generate summaries for multiple texts with limited concurrency."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(text: str, node_type: str, context: Optional[str] = None) -> SummaryResult:
            async with semaphore:
                return await self.generate_summary(text, node_type, context)
        
        # Create tasks
        tasks = []
        for i, (text, node_type) in enumerate(zip(texts, node_types)):
            context = contexts[i] if contexts and i < len(contexts) else None
            tasks.append(generate_with_semaphore(text, node_type, context))
        
        # Execute with limited concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Summary generation failed for item {i}: {result}")
                final_results.append(SummaryResult(
                    original_text=texts[i],
                    summary=f"Summary generation failed: {str(result)}",
                    model_name=self.model,
                    token_count=0
                ))
            else:
                final_results.append(result)
        
        return final_results

class LLMEmbeddingIntegration:
    """
    Coordinates LLM and embedding generation for the indexing pipeline.
    Handles batch processing and database updates.
    """
    
    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        embedding_model: str = "jinaai/jina-embeddings-v2-base-code",
        llm_provider: str = "anthropic",
        llm_model: str = "claude-3-sonnet-20240229"
    ):
        self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.embedding_generator = EmbeddingGenerator(embedding_model)
        self.llm_summarizer = LLMSummarizer(llm_provider, llm_model)
    
    def close(self):
        """Close database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
    
    async def get_nodes_needing_summaries(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """Get nodes that need summary generation."""
        query = """
        MATCH (n)
        WHERE n.raw_code IS NOT NULL 
        AND (n.generated_summary IS NULL OR n.generated_summary = '')
        AND labels(n)[0] IN ['Class', 'Method', 'Function', 'Interface']
        RETURN n.id as id, n.name as name, n.raw_code as raw_code, 
               labels(n)[0] as node_type, n.full_name as full_name
        LIMIT $batch_size
        """
        
        with self.neo4j_driver.session() as session:
            result = session.run(query, batch_size=batch_size)
            return [dict(record) for record in result]
    
    async def get_nodes_needing_embeddings(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """Get nodes that need embedding generation."""
        query = """
        MATCH (n)
        WHERE n.generated_summary IS NOT NULL 
        AND (n.embedding IS NULL OR size(n.embedding) = 0)
        AND labels(n)[0] IN ['File', 'Class', 'Method', 'Function', 'Variable', 'Interface']
        RETURN n.id as id, n.name as name, n.generated_summary as summary,
               n.raw_code as raw_code, labels(n)[0] as node_type
        LIMIT $batch_size
        """
        
        with self.neo4j_driver.session() as session:
            result = session.run(query, batch_size=batch_size)
            return [dict(record) for record in result]
    
    async def update_node_summary(self, node_id: str, summary: str) -> bool:
        """Update a node with generated summary."""
        query = """
        MATCH (n {id: $node_id})
        SET n.generated_summary = $summary
        RETURN n.id as id
        """
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(query, node_id=node_id, summary=summary)
                return result.single() is not None
        except Exception as e:
            logger.error(f"Error updating summary for node {node_id}: {e}")
            return False
    
    async def update_node_embedding(self, node_id: str, embedding: List[float]) -> bool:
        """Update a node with generated embedding."""
        query = """
        MATCH (n {id: $node_id})
        SET n.embedding = $embedding
        RETURN n.id as id
        """
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(query, node_id=node_id, embedding=embedding)
                return result.single() is not None
        except Exception as e:
            logger.error(f"Error updating embedding for node {node_id}: {e}")
            return False
    
    async def process_summaries_batch(self, batch_size: int = 50, max_concurrent: int = 5) -> int:
        """Process a batch of nodes for summary generation."""
        nodes = await self.get_nodes_needing_summaries(batch_size)
        
        if not nodes:
            return 0
        
        logger.info(f"Generating summaries for {len(nodes)} nodes")
        
        # Extract data for batch processing
        texts = [node['raw_code'] for node in nodes]
        node_types = [node['node_type'].lower() for node in nodes]
        
        # Generate summaries
        summary_results = await self.llm_summarizer.generate_summaries_batch(
            texts, node_types, max_concurrent=max_concurrent
        )
        
        # Update database
        successful_updates = 0
        for node, summary_result in zip(nodes, summary_results):
            if await self.update_node_summary(node['id'], summary_result.summary):
                successful_updates += 1
        
        logger.info(f"Updated {successful_updates}/{len(nodes)} node summaries")
        return successful_updates
    
    async def process_embeddings_batch(self, batch_size: int = 100) -> int:
        """Process a batch of nodes for embedding generation."""
        nodes = await self.get_nodes_needing_embeddings(batch_size)
        
        if not nodes:
            return 0
        
        logger.info(f"Generating embeddings for {len(nodes)} nodes")
        
        # Use summaries for embedding, fallback to raw code
        texts = []
        for node in nodes:
            if node['summary'] and node['summary'].strip():
                texts.append(node['summary'])
            elif node['raw_code']:
                texts.append(node['raw_code'][:1000])  # Limit code length
            else:
                texts.append(node['name'])  # Fallback to name
        
        # Generate embeddings
        embedding_results = await self.embedding_generator.generate_embeddings_batch(texts)
        
        # Update database
        successful_updates = 0
        for node, embedding_result in zip(nodes, embedding_results):
            if embedding_result.embedding and await self.update_node_embedding(node['id'], embedding_result.embedding):
                successful_updates += 1
        
        logger.info(f"Updated {successful_updates}/{len(nodes)} node embeddings")
        return successful_updates
    
    async def run_full_enrichment(self, summary_batch_size: int = 50, embedding_batch_size: int = 100) -> Dict[str, int]:
        """Run complete summary and embedding enrichment process."""
        logger.info("Starting LLM and embedding enrichment process")
        
        stats = {
            "summaries_generated": 0,
            "embeddings_generated": 0,
            "total_iterations": 0
        }
        
        # Process summaries in iterations
        while True:
            summary_count = await self.process_summaries_batch(summary_batch_size)
            if summary_count == 0:
                break
            stats["summaries_generated"] += summary_count
            stats["total_iterations"] += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(1)
        
        # Process embeddings in iterations
        while True:
            embedding_count = await self.process_embeddings_batch(embedding_batch_size)
            if embedding_count == 0:
                break
            stats["embeddings_generated"] += embedding_count
            
            # Small delay for processing
            await asyncio.sleep(0.5)
        
        logger.info(f"Enrichment complete: {stats['summaries_generated']} summaries, {stats['embeddings_generated']} embeddings")
        return stats

# Example usage
async def main():
    """Example usage of LLM and embedding integration."""
    integration = LLMEmbeddingIntegration(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    try:
        # Run full enrichment process
        stats = await integration.run_full_enrichment()
        print("Enrichment stats:", stats)
        
    finally:
        integration.close()

if __name__ == "__main__":
    asyncio.run(main()) 