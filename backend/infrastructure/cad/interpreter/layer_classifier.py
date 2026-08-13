from domain.model2d.entities import SemanticLayerType

class LayerClassifier:
    def classify(self, layer_name: str) -> SemanticLayerType:
        name_upper = layer_name.upper()
        if 'MURO' in name_upper or 'WALL' in name_upper or 'PARED' in name_upper:
            return SemanticLayerType.WALLS
        return SemanticLayerType.UNKNOWN
