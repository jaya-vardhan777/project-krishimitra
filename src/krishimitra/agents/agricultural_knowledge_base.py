"""
Agricultural Knowledge Base and RAG System for KrishiMitra Platform

This module implements the agricultural knowledge base using vector databases,
document loaders, and retrieval-augmented generation (RAG) for contextual
agricultural intelligence and research paper processing.
"""

import json
import logging
import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
import numpy as np
from pydantic import BaseModel, Field

# LangChain imports for RAG
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.document_loaders import (
    TextLoader, PDFLoader, CSVLoader, JSONLoader,
    DirectoryLoader, UnstructuredFileLoader
)
from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter, 
    CharacterTextSplitter,
    TokenTextSplitter
)
from langchain_community.embeddings import BedrockEmbeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain.chains import RetrievalQA
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from pydantic import BaseModel as LangChainBaseModel

from ..core.config import get_settings
from .knowledge_reasoning import BedrockLLMManager

logger = logging.getLogger(__name__)
settings = get_settings()


class KnowledgeDocument(BaseModel):
    """Model for agricultural knowledge documents"""
    
    document_id: str = Field(description="Unique document identifier")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content")
    document_type: str = Field(description="Type of document (research_paper, guideline, manual, etc.)")
    source: str = Field(description="Document source")
    language: str = Field(default="english", description="Document language")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeQuery(BaseModel):
    """Model for knowledge base queries"""
    
    query_text: str = Field(description="Query text")
    query_type: str = Field(default="general", description="Type of query")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Query context")
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum number of results")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    include_metadata: bool = Field(default=True, description="Include document metadata")


class KnowledgeSearchResult(BaseModel):
    """Model for knowledge search results"""
    
    document_id: str = Field(description="Document identifier")
    title: str = Field(description="Document title")
    content_snippet: str = Field(description="Relevant content snippet")
    similarity_score: float = Field(description="Similarity score")
    source: str = Field(description="Document source")
    document_type: str = Field(description="Document type")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class AgriculturalEmbeddingsManager:
    """Manages embeddings for agricultural documents using Amazon Bedrock"""
    
    def __init__(self):
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=settings.bedrock_region
        )
        self.embeddings = None
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        """Initialize Bedrock embeddings"""
        try:
            self.embeddings = BedrockEmbeddings(
                client=self.bedrock_client,
                model_id="amazon.titan-embed-text-v1",
                region_name=settings.bedrock_region
            )
            logger.info("Initialized Bedrock embeddings")
        except Exception as e:
            logger.error(f"Error initializing embeddings: {e}")
            raise
    
    def get_embeddings(self) -> BedrockEmbeddings:
        """Get embeddings instance"""
        return self.embeddings
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents"""
        try:
            embeddings = await self.embeddings.aembed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Error embedding documents: {e}")
            return []
    
    async def embed_query(self, text: str) -> List[float]:
        """Embed a single query"""
        try:
            embedding = await self.embeddings.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            return []


class DocumentProcessor:
    """Processes and chunks agricultural documents for vector storage"""
    
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        self.token_splitter = TokenTextSplitter(
            chunk_size=800,
            chunk_overlap=100
        )
    
    async def load_documents_from_directory(self, directory_path: str) -> List[Document]:
        """Load documents from a directory"""
        try:
            documents = []
            directory = Path(directory_path)
            
            if not directory.exists():
                logger.warning(f"Directory does not exist: {directory_path}")
                return documents
            
            # Load different file types
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        docs = await self._load_single_file(file_path)
                        documents.extend(docs)
                    except Exception as e:
                        logger.error(f"Error loading file {file_path}: {e}")
                        continue
            
            logger.info(f"Loaded {len(documents)} documents from {directory_path}")
            return documents
            
        except Exception as e:
            logger.error(f"Error loading documents from directory: {e}")
            return []
    
    async def _load_single_file(self, file_path: Path) -> List[Document]:
        """Load a single file based on its extension"""
        try:
            file_extension = file_path.suffix.lower()
            
            if file_extension == '.txt':
                loader = TextLoader(str(file_path))
            elif file_extension == '.pdf':
                loader = PDFLoader(str(file_path))
            elif file_extension == '.csv':
                loader = CSVLoader(str(file_path))
            elif file_extension == '.json':
                loader = JSONLoader(str(file_path), jq_schema='.', text_content=False)
            else:
                # Try unstructured loader for other formats
                loader = UnstructuredFileLoader(str(file_path))
            
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    'source_file': str(file_path),
                    'file_type': file_extension,
                    'loaded_at': datetime.now(timezone.utc).isoformat()
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")
            return []
    
    async def process_documents(self, documents: List[Document]) -> List[Document]:
        """Process and chunk documents"""
        try:
            processed_docs = []
            
            for doc in documents:
                # Split document into chunks
                chunks = self.text_splitter.split_documents([doc])
                
                # Add chunk metadata
                for i, chunk in enumerate(chunks):
                    chunk.metadata.update({
                        'chunk_id': f"{doc.metadata.get('source_file', 'unknown')}_{i}",
                        'chunk_index': i,
                        'total_chunks': len(chunks),
                        'processed_at': datetime.now(timezone.utc).isoformat()
                    })
                
                processed_docs.extend(chunks)
            
            logger.info(f"Processed {len(documents)} documents into {len(processed_docs)} chunks")
            return processed_docs
            
        except Exception as e:
            logger.error(f"Error processing documents: {e}")
            return []
    
    async def create_knowledge_document(
        self, 
        title: str, 
        content: str, 
        document_type: str = "manual",
        source: str = "internal",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> KnowledgeDocument:
        """Create a knowledge document from raw content"""
        try:
            document = KnowledgeDocument(
                document_id=f"{source}_{title.lower().replace(' ', '_')}_{int(datetime.now().timestamp())}",
                title=title,
                content=content,
                document_type=document_type,
                source=source,
                tags=tags or [],
                metadata=metadata or {}
            )
            
            return document
            
        except Exception as e:
            logger.error(f"Error creating knowledge document: {e}")
            raise


class VectorStoreManager:
    """Manages vector stores for agricultural knowledge"""
    
    def __init__(self, embeddings_manager: AgriculturalEmbeddingsManager):
        self.embeddings_manager = embeddings_manager
        self.vector_stores: Dict[str, VectorStore] = {}
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
        self.knowledge_bucket = settings.model_artifacts_bucket
    
    async def create_faiss_store(
        self, 
        documents: List[Document], 
        store_name: str = "agricultural_knowledge"
    ) -> FAISS:
        """Create FAISS vector store from documents"""
        try:
            if not documents:
                raise ValueError("No documents provided for vector store creation")
            
            # Create FAISS vector store
            vector_store = FAISS.from_documents(
                documents=documents,
                embedding=self.embeddings_manager.get_embeddings()
            )
            
            self.vector_stores[store_name] = vector_store
            logger.info(f"Created FAISS vector store '{store_name}' with {len(documents)} documents")
            
            return vector_store
            
        except Exception as e:
            logger.error(f"Error creating FAISS vector store: {e}")
            raise
    
    async def create_chroma_store(
        self, 
        documents: List[Document], 
        store_name: str = "agricultural_knowledge",
        persist_directory: str = None
    ) -> Chroma:
        """Create Chroma vector store from documents"""
        try:
            if not documents:
                raise ValueError("No documents provided for vector store creation")
            
            # Set default persist directory
            if persist_directory is None:
                persist_directory = f"./chroma_db/{store_name}"
            
            # Create Chroma vector store
            vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings_manager.get_embeddings(),
                persist_directory=persist_directory
            )
            
            self.vector_stores[store_name] = vector_store
            logger.info(f"Created Chroma vector store '{store_name}' with {len(documents)} documents")
            
            return vector_store
            
        except Exception as e:
            logger.error(f"Error creating Chroma vector store: {e}")
            raise
    
    async def load_vector_store(self, store_name: str, store_type: str = "faiss") -> Optional[VectorStore]:
        """Load existing vector store"""
        try:
            if store_type.lower() == "faiss":
                # Load FAISS from S3 or local storage
                store_path = f"./vector_stores/{store_name}"
                if os.path.exists(store_path):
                    vector_store = FAISS.load_local(
                        store_path,
                        self.embeddings_manager.get_embeddings()
                    )
                    self.vector_stores[store_name] = vector_store
                    logger.info(f"Loaded FAISS vector store '{store_name}'")
                    return vector_store
            
            elif store_type.lower() == "chroma":
                # Load Chroma from persist directory
                persist_directory = f"./chroma_db/{store_name}"
                if os.path.exists(persist_directory):
                    vector_store = Chroma(
                        persist_directory=persist_directory,
                        embedding_function=self.embeddings_manager.get_embeddings()
                    )
                    self.vector_stores[store_name] = vector_store
                    logger.info(f"Loaded Chroma vector store '{store_name}'")
                    return vector_store
            
            logger.warning(f"Vector store '{store_name}' not found")
            return None
            
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            return None
    
    async def save_vector_store(self, store_name: str, store_type: str = "faiss") -> bool:
        """Save vector store to persistent storage"""
        try:
            if store_name not in self.vector_stores:
                logger.error(f"Vector store '{store_name}' not found")
                return False
            
            vector_store = self.vector_stores[store_name]
            
            if store_type.lower() == "faiss" and isinstance(vector_store, FAISS):
                # Save FAISS locally
                store_path = f"./vector_stores/{store_name}"
                os.makedirs(os.path.dirname(store_path), exist_ok=True)
                vector_store.save_local(store_path)
                logger.info(f"Saved FAISS vector store '{store_name}'")
                return True
            
            elif store_type.lower() == "chroma" and isinstance(vector_store, Chroma):
                # Chroma auto-persists if persist_directory is set
                logger.info(f"Chroma vector store '{store_name}' auto-persisted")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")
            return False
    
    def get_vector_store(self, store_name: str) -> Optional[VectorStore]:
        """Get vector store by name"""
        return self.vector_stores.get(store_name)
    
    async def add_documents_to_store(
        self, 
        store_name: str, 
        documents: List[Document]
    ) -> bool:
        """Add documents to existing vector store"""
        try:
            if store_name not in self.vector_stores:
                logger.error(f"Vector store '{store_name}' not found")
                return False
            
            vector_store = self.vector_stores[store_name]
            vector_store.add_documents(documents)
            
            logger.info(f"Added {len(documents)} documents to vector store '{store_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {e}")
            return False


class AgriculturalRAGSystem:
    """Retrieval-Augmented Generation system for agricultural knowledge"""
    
    def __init__(self):
        self.llm_manager = BedrockLLMManager()
        self.embeddings_manager = AgriculturalEmbeddingsManager()
        self.vector_store_manager = VectorStoreManager(self.embeddings_manager)
        self.document_processor = DocumentProcessor()
        self.retrievers: Dict[str, BaseRetriever] = {}
        self.qa_chains: Dict[str, RetrievalQA] = {}
    
    async def initialize_knowledge_base(
        self, 
        knowledge_directory: str = "./knowledge_base",
        store_name: str = "agricultural_knowledge",
        store_type: str = "faiss"
    ) -> bool:
        """Initialize the agricultural knowledge base"""
        try:
            # Try to load existing vector store
            vector_store = await self.vector_store_manager.load_vector_store(store_name, store_type)
            
            if vector_store is None:
                # Create new vector store from documents
                logger.info("Creating new knowledge base from documents...")
                
                # Load documents from directory
                documents = await self.document_processor.load_documents_from_directory(knowledge_directory)
                
                if not documents:
                    # Create sample agricultural documents if none exist
                    documents = await self._create_sample_agricultural_documents()
                
                # Process documents
                processed_docs = await self.document_processor.process_documents(documents)
                
                # Create vector store
                if store_type.lower() == "faiss":
                    vector_store = await self.vector_store_manager.create_faiss_store(
                        processed_docs, store_name
                    )
                else:
                    vector_store = await self.vector_store_manager.create_chroma_store(
                        processed_docs, store_name
                    )
                
                # Save vector store
                await self.vector_store_manager.save_vector_store(store_name, store_type)
            
            # Create retriever
            retriever = vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 5}
            )
            self.retrievers[store_name] = retriever
            
            # Create QA chain
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm_manager.get_llm(),
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True
            )
            self.qa_chains[store_name] = qa_chain
            
            logger.info(f"Initialized agricultural knowledge base '{store_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing knowledge base: {e}")
            return False
    
    async def query_knowledge_base(
        self, 
        query: KnowledgeQuery,
        store_name: str = "agricultural_knowledge"
    ) -> List[KnowledgeSearchResult]:
        """Query the agricultural knowledge base"""
        try:
            if store_name not in self.retrievers:
                logger.error(f"Knowledge base '{store_name}' not initialized")
                return []
            
            retriever = self.retrievers[store_name]
            
            # Retrieve relevant documents
            docs = retriever.get_relevant_documents(query.query_text)
            
            # Convert to search results
            results = []
            for i, doc in enumerate(docs[:query.max_results]):
                result = KnowledgeSearchResult(
                    document_id=doc.metadata.get('chunk_id', f'doc_{i}'),
                    title=doc.metadata.get('title', 'Unknown Title'),
                    content_snippet=doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                    similarity_score=1.0 - (i * 0.1),  # Approximate similarity score
                    source=doc.metadata.get('source_file', 'Unknown Source'),
                    document_type=doc.metadata.get('document_type', 'unknown'),
                    metadata=doc.metadata if query.include_metadata else {}
                )
                results.append(result)
            
            logger.info(f"Retrieved {len(results)} results for query: {query.query_text[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Error querying knowledge base: {e}")
            return []
    
    async def get_contextual_answer(
        self, 
        question: str,
        store_name: str = "agricultural_knowledge"
    ) -> Dict[str, Any]:
        """Get contextual answer using RAG"""
        try:
            if store_name not in self.qa_chains:
                logger.error(f"QA chain for '{store_name}' not initialized")
                return {"answer": "Knowledge base not available", "sources": []}
            
            qa_chain = self.qa_chains[store_name]
            
            # Get answer with sources
            result = qa_chain({"query": question})
            
            # Format response
            response = {
                "answer": result["result"],
                "sources": [
                    {
                        "content": doc.page_content[:200] + "...",
                        "metadata": doc.metadata
                    }
                    for doc in result.get("source_documents", [])
                ],
                "confidence": 0.8,  # Placeholder confidence score
                "query": question
            }
            
            logger.info(f"Generated contextual answer for: {question[:50]}...")
            return response
            
        except Exception as e:
            logger.error(f"Error getting contextual answer: {e}")
            return {"answer": "Error processing query", "sources": [], "error": str(e)}
    
    async def add_knowledge_document(
        self, 
        document: KnowledgeDocument,
        store_name: str = "agricultural_knowledge"
    ) -> bool:
        """Add a new document to the knowledge base"""
        try:
            # Convert to LangChain document
            langchain_doc = Document(
                page_content=document.content,
                metadata={
                    "document_id": document.document_id,
                    "title": document.title,
                    "document_type": document.document_type,
                    "source": document.source,
                    "language": document.language,
                    "tags": document.tags,
                    "created_at": document.created_at.isoformat(),
                    **document.metadata
                }
            )
            
            # Process document
            processed_docs = await self.document_processor.process_documents([langchain_doc])
            
            # Add to vector store
            success = await self.vector_store_manager.add_documents_to_store(
                store_name, processed_docs
            )
            
            if success:
                logger.info(f"Added document '{document.title}' to knowledge base")
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding document to knowledge base: {e}")
            return False
    
    async def _create_sample_agricultural_documents(self) -> List[Document]:
        """Create sample agricultural documents for testing"""
        try:
            sample_docs = [
                {
                    "title": "Wheat Cultivation Guidelines",
                    "content": """
                    Wheat is one of the most important cereal crops in India. Best practices for wheat cultivation include:
                    
                    1. Soil Preparation: Well-drained loamy soil with pH 6.0-7.5 is ideal for wheat cultivation.
                    2. Sowing Time: October to December is the optimal sowing period for wheat in most regions.
                    3. Seed Rate: Use 100-125 kg seeds per hectare for timely sown wheat.
                    4. Fertilizer Application: Apply 120 kg N, 60 kg P2O5, and 40 kg K2O per hectare.
                    5. Irrigation: Provide irrigation at crown root initiation, tillering, jointing, flowering, and grain filling stages.
                    6. Pest Management: Monitor for aphids, termites, and rust diseases regularly.
                    7. Harvesting: Harvest when grains reach physiological maturity, typically 110-130 days after sowing.
                    """,
                    "document_type": "cultivation_guide",
                    "source": "agricultural_extension"
                },
                {
                    "title": "Rice Farming Best Practices",
                    "content": """
                    Rice is the staple food crop of India. Key practices for successful rice cultivation:
                    
                    1. Land Preparation: Puddle the field thoroughly to create a mud layer for water retention.
                    2. Variety Selection: Choose varieties based on duration, yield potential, and local conditions.
                    3. Nursery Management: Raise healthy seedlings in well-prepared nursery beds.
                    4. Transplanting: Transplant 21-25 day old seedlings with 2-3 seedlings per hill.
                    5. Water Management: Maintain 2-5 cm water level throughout the growing period.
                    6. Nutrient Management: Apply fertilizers based on soil test recommendations.
                    7. Weed Control: Use pre-emergence and post-emergence herbicides as needed.
                    8. Disease Management: Monitor for blast, bacterial blight, and sheath blight.
                    """,
                    "document_type": "cultivation_guide",
                    "source": "agricultural_extension"
                },
                {
                    "title": "Integrated Pest Management",
                    "content": """
                    Integrated Pest Management (IPM) is a sustainable approach to managing pests:
                    
                    1. Prevention: Use resistant varieties, crop rotation, and proper sanitation.
                    2. Monitoring: Regular field scouting to identify pest problems early.
                    3. Biological Control: Encourage natural enemies and use bio-pesticides.
                    4. Cultural Control: Adjust planting dates, spacing, and cultivation practices.
                    5. Chemical Control: Use pesticides only when necessary and follow label instructions.
                    6. Economic Threshold: Apply control measures only when pest levels exceed economic thresholds.
                    7. Record Keeping: Maintain detailed records of pest occurrences and control measures.
                    """,
                    "document_type": "pest_management",
                    "source": "ipm_guidelines"
                },
                {
                    "title": "Soil Health Management",
                    "content": """
                    Maintaining soil health is crucial for sustainable agriculture:
                    
                    1. Soil Testing: Conduct regular soil tests to assess nutrient status and pH.
                    2. Organic Matter: Add compost, farmyard manure, and crop residues to improve soil structure.
                    3. Cover Crops: Use cover crops to prevent erosion and add organic matter.
                    4. Crop Rotation: Rotate crops to break pest cycles and improve soil fertility.
                    5. Minimal Tillage: Reduce tillage to preserve soil structure and organic matter.
                    6. Balanced Fertilization: Apply fertilizers based on soil test recommendations.
                    7. Lime Application: Apply lime to correct soil acidity when pH is below 6.0.
                    8. Drainage: Ensure proper drainage to prevent waterlogging and salt accumulation.
                    """,
                    "document_type": "soil_management",
                    "source": "soil_health_program"
                }
            ]
            
            documents = []
            for doc_data in sample_docs:
                doc = Document(
                    page_content=doc_data["content"],
                    metadata={
                        "title": doc_data["title"],
                        "document_type": doc_data["document_type"],
                        "source": doc_data["source"],
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                documents.append(doc)
            
            logger.info(f"Created {len(documents)} sample agricultural documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error creating sample documents: {e}")
            return []


class AgriculturalKnowledgeTool(BaseTool, LangChainBaseModel):
    """LangChain tool for agricultural knowledge retrieval"""
    
    name: str = "agricultural_knowledge_search"
    description: str = "Search agricultural knowledge base for relevant information and best practices"
    
    def __init__(self, rag_system: AgriculturalRAGSystem):
        super().__init__()
        self.rag_system = rag_system
    
    def _run(self, query: str) -> str:
        """Run the knowledge search tool"""
        try:
            # Create query object
            knowledge_query = KnowledgeQuery(
                query_text=query,
                max_results=3
            )
            
            # Search knowledge base (synchronous version)
            # In production, this would be properly async
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            results = loop.run_until_complete(
                self.rag_system.query_knowledge_base(knowledge_query)
            )
            
            # Format results
            if results:
                formatted_results = []
                for result in results:
                    formatted_results.append(
                        f"Title: {result.title}\n"
                        f"Source: {result.source}\n"
                        f"Content: {result.content_snippet}\n"
                        f"Relevance: {result.similarity_score:.2f}\n"
                    )
                return "\n---\n".join(formatted_results)
            else:
                return "No relevant information found in the knowledge base."
            
        except Exception as e:
            logger.error(f"Error in knowledge search tool: {e}")
            return f"Error searching knowledge base: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the tool"""
        try:
            # Create query object
            knowledge_query = KnowledgeQuery(
                query_text=query,
                max_results=3
            )
            
            # Search knowledge base
            results = await self.rag_system.query_knowledge_base(knowledge_query)
            
            # Format results
            if results:
                formatted_results = []
                for result in results:
                    formatted_results.append(
                        f"Title: {result.title}\n"
                        f"Source: {result.source}\n"
                        f"Content: {result.content_snippet}\n"
                        f"Relevance: {result.similarity_score:.2f}\n"
                    )
                return "\n---\n".join(formatted_results)
            else:
                return "No relevant information found in the knowledge base."
            
        except Exception as e:
            logger.error(f"Error in async knowledge search tool: {e}")
            return f"Error searching knowledge base: {str(e)}"


class AgriculturalKnowledgeBase:
    """Main Agricultural Knowledge Base class"""
    
    def __init__(self):
        self.rag_system = AgriculturalRAGSystem()
        self.tools = []
        self.initialized = False
    
    async def initialize(
        self, 
        knowledge_directory: str = "./knowledge_base",
        store_name: str = "agricultural_knowledge"
    ) -> bool:
        """Initialize the knowledge base"""
        try:
            success = await self.rag_system.initialize_knowledge_base(
                knowledge_directory, store_name
            )
            
            if success:
                # Create tools
                knowledge_tool = AgriculturalKnowledgeTool(self.rag_system)
                self.tools = [knowledge_tool]
                self.initialized = True
                logger.info("Agricultural Knowledge Base initialized successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Error initializing Agricultural Knowledge Base: {e}")
            return False
    
    async def search(self, query: str, max_results: int = 5) -> List[KnowledgeSearchResult]:
        """Search the knowledge base"""
        if not self.initialized:
            logger.error("Knowledge base not initialized")
            return []
        
        knowledge_query = KnowledgeQuery(
            query_text=query,
            max_results=max_results
        )
        
        return await self.rag_system.query_knowledge_base(knowledge_query)
    
    async def get_answer(self, question: str) -> Dict[str, Any]:
        """Get contextual answer using RAG"""
        if not self.initialized:
            logger.error("Knowledge base not initialized")
            return {"answer": "Knowledge base not initialized", "sources": []}
        
        return await self.rag_system.get_contextual_answer(question)
    
    async def add_document(self, document: KnowledgeDocument) -> bool:
        """Add document to knowledge base"""
        if not self.initialized:
            logger.error("Knowledge base not initialized")
            return False
        
        return await self.rag_system.add_knowledge_document(document)
    
    def get_tools(self) -> List[BaseTool]:
        """Get LangChain tools for the knowledge base"""
        return self.tools
    
    async def close(self):
        """Close knowledge base connections"""
        try:
            # Clean up resources if needed
            logger.info("Agricultural Knowledge Base closed")
        except Exception as e:
            logger.error(f"Error closing Agricultural Knowledge Base: {e}")