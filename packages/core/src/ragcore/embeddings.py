from ..config import settings

class EmbeddingModels:
    """Offline loaders for bge-m3, SigLIP, and reranker."""
    def __init__(self):
        self.text_model = None
        self.image_model = None
        
    def load_text_model(self):
        # TODO: Implement offline loading of BAAI/bge-m3 using settings.bge_m3_path
        pass
        
    def load_image_model(self):
        # TODO: Implement offline loading of Google SigLIP using settings.siglip_path
        pass

embedding_models = EmbeddingModels()
